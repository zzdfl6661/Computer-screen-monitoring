from .activity import router as activity_router
from .stats import router as stats_router
from .distribution import router as distribution_router
from .trend import router as trend_router
from .search import router as search_router
from .feedback import router as feedback_router
from .privacy import router as privacy_router
from .vision import router as vision_router
from .label import router as label_router

activity = activity_router
stats = stats_router
distribution = distribution_router
trend = trend_router
search = search_router
feedback = feedback_router
privacy = privacy_router
vision = vision_router
label = label_router