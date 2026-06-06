from sqlalchemy import (
    Integer, String, Text, Boolean, DateTime, Date, ForeignKey, 
    UniqueConstraint, Index, JSON
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime, date

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    # Relationships
    owned_boards = relationship("Board", back_populates="owner")
    board_memberships = relationship("BoardMember", back_populates="user", cascade="all, delete-orphan")
    assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")

class Board(Base):
    __tablename__ = "boards"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    # Relationships
    owner = relationship("User", back_populates="owned_boards")
    members = relationship("BoardMember", back_populates="board", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="board", cascade="all, delete-orphan")
    invitations = relationship("Invitation", back_populates="board", cascade="all, delete-orphan")

class BoardMember(Base):
    __tablename__ = "board_members"
    __table_args__ = (
        UniqueConstraint('board_id', 'user_id', name='uq_board_user'),
        Index('idx_board_members_board_user', 'board_id', 'user_id'),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    board_id: Mapped[int] = mapped_column(Integer, ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String)  # admin / member
    role: Mapped[str] = mapped_column(String)    # mentor / student
    is_creator: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    invited_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    board = relationship("Board", back_populates="members")
    user = relationship("User", back_populates="board_memberships")
    inviter = relationship("User", foreign_keys=[invited_by])

class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index('idx_tasks_board_column', 'board_id', 'column'),
        Index('idx_tasks_board_substatus', 'board_id', 'substatus'),
        Index('idx_tasks_assignee_status', 'assignee_id', 'column'),
        Index('idx_tasks_created_at', 'created_at'),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    board_id: Mapped[int] = mapped_column(Integer, ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    column: Mapped[str] = mapped_column(String)          # not_started / in_progress / done
    substatus: Mapped[str | None] = mapped_column(String, nullable=True) # in_review / accepted / returned
    priority: Mapped[str] = mapped_column(String)        # high / med / low
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    assignee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    tags: Mapped[list | None] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    board = relationship("Board", back_populates="tasks")
    assignee = relationship("User", back_populates="assigned_tasks", foreign_keys=[assignee_id])
    subtasks = relationship("Subtask", back_populates="task", cascade="all, delete-orphan")
    files = relationship("File", back_populates="task", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="task", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="task", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="task", cascade="all, delete-orphan")

class Subtask(Base):
    __tablename__ = "subtasks"
    __table_args__ = (
        Index('idx_subtasks_task_order', 'task_id', 'order'),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer)
    
    task = relationship("Task", back_populates="subtasks")

class File(Base):
    __tablename__ = "files"
    __table_args__ = (
        Index('idx_files_task', 'task_id'),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String)
    original_filename: Mapped[str] = mapped_column(String)
    file_path: Mapped[str] = mapped_column(String)
    mime_type: Mapped[str] = mapped_column(String)
    size: Mapped[int] = mapped_column(Integer)
    is_mentor_file: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    task = relationship("Task", back_populates="files")
    user = relationship("User")

class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index('idx_comments_task_created', 'task_id', 'created_at'),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    
    task = relationship("Task", back_populates="comments")
    user = relationship("User")

class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        Index('idx_submissions_task_status', 'task_id', 'status'),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[str] = mapped_column(String)  # pending / accepted / returned
    mentor_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    
    task = relationship("Task", back_populates="submissions")
    reviewer = relationship("User")

class ActivityLog(Base):
    __tablename__ = "activity_log"
    __table_args__ = (
        Index('idx_activity_task_created', 'task_id', 'created_at'),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String)
    old_value: Mapped[str | None] = mapped_column(String, nullable=True)
    new_value: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    
    task = relationship("Task", back_populates="activity_logs")
    user = relationship("User")

class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (
        Index('idx_invitations_token', 'token'),
        Index('idx_invitations_email', 'invited_email'),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    board_id: Mapped[int] = mapped_column(Integer, ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    invited_email: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String)  # pending / accepted / expired
    invited_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    
    board = relationship("Board", back_populates="invitations")
    invited_by = relationship("User")