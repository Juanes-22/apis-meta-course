from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from .models import MenuItem, CartItem, Order, OrderItem, Category

from django.contrib.auth.models import User, Group


class ManagerUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class DeliveryCrewUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "email"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "title"]

class MenuItemSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()
    category_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = MenuItem
        fields = ["id", "title", "price", "featured", "category", "category_id"]


class OrderSerializer(serializers.ModelSerializer):
    delivery_crew_id = serializers.IntegerField(
        write_only=True, allow_null=True, required=False
    )

    class Meta:
        model = Order
        fields = ["id", "delivery_crew_id", "status", "total", "date"]
        read_only_fields = [
            "status",
            "date",
            "total",
        ]

    def _get_and_validate_delivery_crew(self, delivery_crew_id: int) -> User:
        try:
            delivery_crew = User.objects.get(id=delivery_crew_id)
        except User.DoesNotExist:
            raise serializers.ValidationError("Delivery crew user does not exist.")

        if not delivery_crew.groups.filter(name="Delivery crew").exists():
            raise serializers.ValidationError(
                "Input delivery crew ID is not in delivery crew group."
            )

        return delivery_crew


class CustomerOrderSerializer(OrderSerializer):
    def create(self, validated_data):
        user = self.context["request"].user
        cart_items = self.context["cart_items"]
        delivery_crew_id = validated_data.get("delivery_crew_id")
        delivery_crew = (
            self._get_and_validate_delivery_crew(delivery_crew_id)
            if delivery_crew_id is not None
            else None
        )

        return Order.objects.create(
            user=user,
            delivery_crew=delivery_crew,
            status=False,
            total=sum(cart_item.price for cart_item in cart_items),
        )


class ManagerOrderSerializer(OrderSerializer):
    user = ManagerUserSerializer(read_only=True)
    delivery_crew = ManagerUserSerializer(read_only=True)

    class Meta(OrderSerializer.Meta):
        fields = [
            "id",
            "user",
            "delivery_crew_id",
            "delivery_crew",
            "status",
            "total",
            "date",
        ]
        read_only_fields = [
            "date",
            "total",
        ]

    def update(self, instance, validated_data):
        try:
            delivery_crew_id = validated_data["delivery_crew_id"]
            delivery_crew = (
                self._get_and_validate_delivery_crew(delivery_crew_id)
                if delivery_crew_id is not None
                else None
            )
        except KeyError:
            delivery_crew = instance.delivery_crew

        status = validated_data.get("status", instance.status)

        instance.delivery_crew = delivery_crew
        instance.status = status
        instance.save()
        return instance


class DeliveryCrewOrderSerializer(OrderSerializer):
    user = DeliveryCrewUserSerializer(read_only=True)

    class Meta(OrderSerializer.Meta):
        fields = [
            "id",
            "user",
            "status",
            "total",
            "date",
        ]
        read_only_fields = [
            "date",
            "total",
        ]

    def update(self, instance, validated_data):
        instance.status = validated_data.get("status", instance.status)
        instance.save()
        return instance


class CartItemSerializer(serializers.ModelSerializer):
    menuitem = MenuItemSerializer(read_only=True)
    menuitem_id = serializers.IntegerField(write_only=True)
    subtotal_price = serializers.CharField(source="price", read_only=True)

    class Meta:
        model = CartItem
        fields = [
            "id",
            "menuitem_id",
            "menuitem",
            "quantity",
            "subtotal_price",
        ]

    def create(self, validated_data):
        user = self.context["request"].user
        menuitem_id = validated_data["menuitem_id"]
        quantity = validated_data["quantity"]

        try:
            menuitem = MenuItem.objects.get(pk=menuitem_id)
        except MenuItem.DoesNotExist:
            raise serializers.ValidationError("Menu item does not exist.")

        return CartItem.objects.create(
            user=user,
            menuitem=menuitem,
            quantity=quantity,
            unit_price=menuitem.price,
            price=menuitem.price * quantity,
        )

    def validate(self, data):
        menuitem_id = data["menuitem_id"]
        user = self.context["request"].user

        if CartItem.objects.filter(menuitem_id=menuitem_id, user=user).exists():
            raise serializers.ValidationError("Menu item already in user cart")

        return data


class OrderItemSerializer(serializers.ModelSerializer):
    menuitem = MenuItemSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "menuitem",
            "quantity",
            "unit_price",
            "price",
        ]
