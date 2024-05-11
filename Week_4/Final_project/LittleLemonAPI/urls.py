from django.urls import path, include
from . import views

urlpatterns = [
    path("", include("djoser.urls")),
    path("", include("djoser.urls.authtoken")),
    path("cart/menu-items", views.cart_items),
    path(
        "menu-items",
        views.MenuItemsViewSet.as_view(
            {
                "get": "list",
                "post": "create",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
    ),
    path(
        "menu-items/<int:pk>",
        views.MenuItemsViewSet.as_view(
            {
                "get": "retrieve",
                "post": "create",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
    ),
    path("categories", views.CategoriesListCreateView.as_view()),
    path("orders", views.OrdersListCreateView.as_view()),
    path("orders/<int:pk>", views.SingleOrderView.as_view()),
    path("groups/<str:group_name>/users", views.group_users),
    path("groups/<str:group_name>/users/<int:pk>", views.single_group_user),
]
