from rest_framework import generics
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes

from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from .models import MenuItem, CartItem, Order, OrderItem, Category
from .serializers import (
    MenuItemSerializer,
    CartItemSerializer,
    CustomerOrderSerializer,
    ManagerOrderSerializer,
    DeliveryCrewOrderSerializer,
    OrderItemSerializer,
    ManagerUserSerializer,
    CategorySerializer,
)

from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User, Group


# menu items endpoints


class MenuItemsViewSet(viewsets.ModelViewSet):
    queryset = MenuItem.objects.select_related("category").all()
    serializer_class = MenuItemSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ["price", "title"]
    search_fields = ["title", "category__title"]
    filterset_fields = ["category__title", "featured"]

    def create(self, request, *args, **kwargs):
        if request.user.groups.filter(name="Manager").exists():
            serialized_item = MenuItemSerializer(data=request.data)
            serialized_item.is_valid(raise_exception=True)
            serialized_item.save()
            return Response(serialized_item.data, status.HTTP_201_CREATED)
        else:
            return Response(
                {"error": "You are not authorized"}, status.HTTP_403_FORBIDDEN
            )

    def update(self, request, pk=None):
        if request.user.groups.filter(name="Manager").exists():
            if pk is None:
                return Response(
                    {"error": "Menu item ID not provided in URL"},
                    status.HTTP_400_BAD_REQUEST,
                )

            item = get_object_or_404(MenuItem, pk=pk)
            serialized_item = MenuItemSerializer(item, data=request.data)
            serialized_item.is_valid(raise_exception=True)
            serialized_item.save()
            return Response(serialized_item.data, status.HTTP_201_CREATED)
        else:
            return Response(
                {"error": "You are not authorized in URL"}, status.HTTP_403_FORBIDDEN
            )

    def retrieve(self, request, pk=None):
        item = get_object_or_404(MenuItem, pk=pk)
        serialized_item = MenuItemSerializer(item)
        return Response(serialized_item.data)

    def partial_update(self, request, pk=None):
        if request.user.groups.filter(name="Manager").exists():
            if pk is None:
                return Response(
                    {"error": "Menu item ID not provided in URL"},
                    status.HTTP_400_BAD_REQUEST,
                )

            item = get_object_or_404(MenuItem, pk=pk)
            serialized_item = MenuItemSerializer(item, data=request.data, partial=True)
            serialized_item.is_valid(raise_exception=True)
            serialized_item.save()
            return Response(serialized_item.data, status.HTTP_200_OK)
        else:
            return Response(
                {"error": "You are not authorized"}, status.HTTP_403_FORBIDDEN
            )

    def destroy(self, request, pk=None):
        if request.user.groups.filter(name="Manager").exists():
            if pk is None:
                return Response(
                    {"error": "Menu item ID not provided in URL"},
                    status.HTTP_400_BAD_REQUEST,
                )

            item = get_object_or_404(MenuItem, pk=pk)
            item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(
                {"error": "You are not authorized"}, status.HTTP_403_FORBIDDEN
            )


# group users endpoints

GROUP_NAMES_MAPPING = {"delivery-crew": "Delivery crew", "manager": "Manager"}


@api_view(["GET", "POST"])
@permission_classes([IsAdminUser])
def group_users(request, group_name):
    if group_name not in GROUP_NAMES_MAPPING:
        return Response({"error": "Group not supported"})

    real_group_name = GROUP_NAMES_MAPPING[group_name]
    users_from_group = User.objects.filter(groups__name=real_group_name)

    if request.method == "GET":
        serializer = ManagerUserSerializer(users_from_group, many=True)
        return Response(serializer.data, status.HTTP_200_OK)

    if request.method == "POST":
        username = request.data.get("username")
        if not username:
            return Response(
                {"error": "Missing username field"}, status.HTTP_400_BAD_REQUEST
            )

        user = get_object_or_404(User, username=username)
        group = Group.objects.get(name=real_group_name)

        group.user_set.add(user)
        return Response(
            {
                "message": f"User {username} added to group {real_group_name} successfully."
            },
            status.HTTP_200_OK,
        )


@api_view(["DELETE"])
@permission_classes([IsAdminUser])
def single_group_user(request, group_name, pk):
    if group_name not in GROUP_NAMES_MAPPING:
        return Response({"error": "Group not supported"})

    real_group_name = GROUP_NAMES_MAPPING[group_name]
    group = Group.objects.get(name=real_group_name)
    user = get_object_or_404(User, pk=pk)

    if request.method == "DELETE":
        group.user_set.remove(user)
        return Response(
            {
                "message": f"User {user.username} removed from group {real_group_name} successfully."
            },
            status.HTTP_200_OK,
        )


# cart items endpoints


@api_view(["GET", "POST", "DELETE"])
@permission_classes([IsAuthenticated])
def cart_items(request):
    is_customer = not request.user.groups.filter(
        name__in=["Manager", "Delivery crew"]
    ).exists()
    if not is_customer:
        return Response({"error": "Not a customer"}, status.HTTP_400_BAD_REQUEST)

    user_cart_items = CartItem.objects.filter(user=request.user)

    if request.method == "GET":
        serializer = CartItemSerializer(user_cart_items, many=True)
        return Response(serializer.data, status.HTTP_200_OK)

    if request.method == "POST":
        # example body: {"menuitem_id": 1, "quantity": 3}
        serialized_item = CartItemSerializer(
            data=request.data, context={"request": request}
        )
        serialized_item.is_valid(raise_exception=True)
        serialized_item.save()
        return Response(serialized_item.data, status.HTTP_201_CREATED)

    if request.method == "DELETE":
        user_cart_items.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# orders endpoints


class OrdersListCreateView(generics.ListCreateAPIView):
    queryset = Order.objects.all()
    permission_classes = [IsAuthenticated]
    ordering_fields = ["date", "total"]
    search_fields = ["user__username", "delivery_crew__username"]
    filterset_fields = ["status"]

    def create(self, request, *args, **kwargs):
        # example body: {}
        is_customer = not request.user.groups.filter(
            name__in=["Manager", "Delivery crew"]
        ).exists()
        if not is_customer:
            return Response({"error": "Not a customer"}, status.HTTP_400_BAD_REQUEST)

        # get current user cart items
        cart_items = CartItem.objects.filter(user=request.user)
        if not cart_items:
            return Response({"error": "Cart is empty"}, status.HTTP_400_BAD_REQUEST)

        # validate data
        serializer_class = self.get_serializer_class()
        serialized_order = serializer_class(
            data=request.data, context={"request": request, "cart_items": cart_items}
        )
        serialized_order.is_valid(raise_exception=True)
        created_order = serialized_order.save()

        # add order items
        for cart_item in cart_items:
            OrderItem.objects.create(
                order=created_order,
                menuitem=cart_item.menuitem,
                quantity=cart_item.quantity,
                unit_price=cart_item.unit_price,
                price=cart_item.price,
            )

        # delete user cart items
        cart_items.delete()

        return Response(serialized_order.data, status.HTTP_201_CREATED)

    def get_queryset(self):
        if self.request.user.groups.filter(name="Delivery crew").exists():
            queryset = Order.objects.filter(delivery_crew=self.request.user)
        elif self.request.user.groups.filter(name="Manager").exists():
            queryset = Order.objects.all()
        else:
            queryset = Order.objects.filter(user=self.request.user)
        return queryset

    def get_serializer_class(self):
        if self.request.user.groups.filter(name="Manager").exists():
            return ManagerOrderSerializer
        elif self.request.user.groups.filter(name="Delivery crew").exists():
            return DeliveryCrewOrderSerializer
        else:
            return CustomerOrderSerializer


class SingleOrderView(generics.RetrieveUpdateAPIView, generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]

    def retrieve(self, request, pk):
        # return all order items from provided user order ID
        orders = self.get_queryset()
        order = get_object_or_404(orders, pk=pk)
        order_items = OrderItem.objects.filter(order=order)
        serializer = OrderItemSerializer(order_items, many=True)
        return Response(serializer.data, status.HTTP_200_OK)

    def partial_update(self, request, pk=None):
        orders = self.get_queryset()
        order = get_object_or_404(orders, pk=pk)
        serializer_class = self.get_serializer_class()
        serialized_order = serializer_class(order, data=request.data, partial=True)
        serialized_order.is_valid(raise_exception=True)
        serialized_order.save()
        return Response(serialized_order.data, status.HTTP_200_OK)

    def get_queryset(self):
        if self.request.user.groups.filter(name="Delivery crew").exists():
            queryset = Order.objects.filter(delivery_crew=self.request.user)
        elif self.request.user.groups.filter(name="Manager").exists():
            queryset = Order.objects.all()
        else:
            queryset = Order.objects.filter(user=self.request.user)
        return queryset

    def get_serializer_class(self):
        if self.request.user.groups.filter(name="Manager").exists():
            return ManagerOrderSerializer
        elif self.request.user.groups.filter(name="Delivery crew").exists():
            return DeliveryCrewOrderSerializer
        else:
            return CustomerOrderSerializer

    def destroy(self, request, pk=None):
        if request.user.groups.filter(name="Manager").exists():
            if pk is None:
                return Response(
                    {"error": "Menu item ID not provided in URL"},
                    status.HTTP_400_BAD_REQUEST,
                )

            order = get_object_or_404(Order, pk=pk)
            order.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(
                {"error": "You are not authorized"}, status.HTTP_403_FORBIDDEN
            )


# categories endpoints


class CategoriesListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = CategorySerializer

    def create(self, request, *args, **kwargs):
        if request.user.groups.filter(name="Manager").exists():
            serialized_item = CategorySerializer(data=request.data)
            serialized_item.is_valid(raise_exception=True)
            serialized_item.save()
            return Response(serialized_item.data, status.HTTP_201_CREATED)
        else:
            return Response(
                {"error": "You are not authorized"}, status.HTTP_403_FORBIDDEN
            )
