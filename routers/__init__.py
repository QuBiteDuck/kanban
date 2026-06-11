from routers.auth import router as auth_router
from routers.boards import router as boards_router
from routers.invitations import router as invitations_router
from routers.tasks import router as tasks_router
from routers.results import router as results_router
from routers.files import router as files_router

__all__ = [
    "auth_router",
    "boards_router",
    "invitations_router",
    "tasks_router",
    "results_router",
    "files_router",
]