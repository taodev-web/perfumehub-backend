import random
import string 
import stripe  
from rest_framework import generics
from .models import Product, Category, Order, OrderItem, Review, DeliveryAddress, RefundRequest, ProductImage
from .serializers import ProductSerializer, CategorySerializer, CartCheckoutSerializer, OrderSerializer, RefundRequestSerializer, RestockSerializer, UpdateOrderStatusSerializer, DeliveryAddressSerializer, CouponSerializer, Coupon, ReviewSerializer, UserRegisterSerializer, UserProfileSerializer, ProductImageSerializer
from django.http import HttpResponse
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from django.contrib.auth.models import User
from rest_framework.permissions import AllowAny
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Sum
from django.utils.dateparse import parse_date
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings  # if not already importe


# This view is for listing all orders for admin users
class AdminOrderListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            queryset = Order.objects.all().order_by('-created_at')

            # Optional status filter
            status_param = request.GET.get('status')
            if status_param:
                queryset = queryset.filter(status=status_param)

            serializer = OrderSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"An error occurred while fetching orders: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Cart Checkout API
# This API allows users to checkout their cart and place an order
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def checkout(request):
    try:
        serializer = CartCheckoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        items = serializer.validated_data['items']
        total = 0

        # Handle coupon
        coupon_code = request.data.get('coupon_code')
        coupon = None
        discount_amount = 0

        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code, active=True)
                if coupon.expiry_date and coupon.expiry_date < timezone.now():
                    coupon = None
                else:
                    subtotal = sum(Product.objects.get(id=item['product_id']).price * item['quantity'] for item in items)
                    discount_amount = (coupon.discount / 100) * subtotal
            except Coupon.DoesNotExist:
                coupon = None

        # Create order
        order = Order.objects.create(
            user=request.user,
            total_price=0,
            coupon=coupon,
            discount_amount=discount_amount
        )

        # Create order items
        for item in items:
            product = Product.objects.get(id=item['product_id'])
            quantity = item['quantity']
            price = product.price * quantity

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=price
            )

            product.quantity -= quantity
            product.save()

            # Stock alert
            if product.quantity < 5:
                send_mail(
                    subject=f"⚠️ Low Stock Alert: {product.name}",
                    message=f"The stock for {product.name} is running low.\n\nOnly {product.quantity} units remaining.\nConsider restocking soon.",
                    from_email=None,
                    recipient_list=['youremail@gmail.com'],
                    fail_silently=False
                )

            total += price

        # Apply discount
        final_total = total - discount_amount
        order.total_price = final_total
        order.save()

        # Build order email
        order_items = OrderItem.objects.filter(order=order)
        item_list = "\n".join(
            [f"- {item.product.name} (x{item.quantity}) - £{item.price}" for item in order_items]
        )

        tracking_info = order.tracking_number if order.tracking_number else "Pending"

        order_message = f"""
Hello {request.user.username},

Thank you for your order with PerfumeHub UK!
Here are your order details:

Order Number: {order.id}
Status: {order.status}
Total: £{order.total_price}
Tracking Number: {tracking_info}

Items:
{item_list}

We’ll notify you when your order status updates.

Thanks for shopping with us!
PerfumeHub UK Team
"""

        # Send confirmation email
        send_mail(
            subject=f"PerfumeHub Order Confirmation — Order #{order.id}",
            message=order_message,
            from_email=None,
            recipient_list=[request.user.email],
            fail_silently=False
        )

        # Stripe PaymentIntent
        stripe.api_key = settings.STRIPE_SECRET_KEY

        payment_intent = stripe.PaymentIntent.create(
            amount=int(final_total * 100),
            currency='gbp',
            metadata={'order_id': str(order.id), 'user': request.user.username}
        )

        return Response({
            'message': 'Order placed successfully',
            'order_id': str(order.id),
            'discount_applied': discount_amount,
            'final_total': final_total,
            'payment_client_secret': payment_intent.client_secret
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )





# Registration API
@api_view(['POST'])
@permission_classes([])
def register(request):
    serializer = UserRegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()

        token, created = Token.objects.get_or_create(user=user)

        # ✅ Send welcome email (fixed recipient_list typo)
        send_mail(
            subject='Welcome to PerfumeHub!',
            message=f'Hello {user.username},\n\nThank you for signing up with PerfumeHub UK.\nWe’re thrilled to have you here. Enjoy shopping premium perfumes!',
            from_email=None,  # Uses DEFAULT_FROM_EMAIL from settings
            recipient_list=[user.email],  # ✅ Correct here!
            fail_silently=False
        )

        return Response({
            'token': token.key,
            'user_id': user.id,
            'username': user.username
        }, status=201)

    return Response(serializer.errors, status=400)

# Login API (DRF built-in)
class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        token = Token.objects.get(key=response.data['token'])
        return Response({'token': token.key, 'user_id': token.user_id, 'username': token.user.username})




# API views for Product and Category
class ProductListView(generics.ListCreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = []  # Public
    http_method_names = ['get', 'post']  # No 'put', 'delete'


# This view is for retrieving a single product by its ID
class ProductDetailView(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = []
    http_method_names = ['get']


class ProductUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'put', 'patch', 'delete']


# This view is for retrieving a list of categories
class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class OrderHistoryView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).order_by('-created_at')
 

# Sales Report API
@api_view(['GET'])
@permission_classes([IsAdminUser])
def sales_report(request):
    # Optional query params
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    orders = Order.objects.all()

    if start_date:
        start_date = parse_date(start_date)
        orders = orders.filter(created_at__date__gte=start_date)
    if end_date:
        end_date = parse_date(end_date)
        orders = orders.filter(created_at__date__lte=end_date)

    total_orders = orders.count()
    total_sales = orders.aggregate(Sum('total_price'))['total_price__sum'] or 0

    top_products = (
        OrderItem.objects
        .filter(order__in=orders)
        .values('product__name')
        .annotate(total_quantity=Sum('quantity'))
        .order_by('-total_quantity')[:5]
    )

    return Response({
        'total_orders': total_orders,
        'total_sales': total_sales,
        'top_products': top_products
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def restock_product(request):
    serializer = RestockSerializer(data=request.data)
    if serializer.is_valid():
        product_id = serializer.validated_data['product_id']
        quantity = serializer.validated_data['quantity']

        product = Product.objects.get(id=product_id)
        product.quantity += quantity
        product.save()

        return Response({
            "message": f"{quantity} units added to {product.name}. New stock: {product.quantity}"
        })

    return Response(serializer.errors, status=400)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def low_stock_products(request):
    threshold = int(request.GET.get('threshold', 5))  # default to 5 if not passed
    low_stock = Product.objects.filter(quantity__lt=threshold)

    serializer = ProductSerializer(low_stock, many=True)
    return Response({
        "threshold": threshold,
        "count": low_stock.count(),
        "low_stock_products": serializer.data
    })

# Update Order Status API
@api_view(['POST'])
@permission_classes([IsAdminUser])
def update_order_status(request, order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=404)

    serializer = UpdateOrderStatusSerializer(data=request.data)
    if serializer.is_valid():
        order.status = serializer.validated_data['status']
        order.save()

        # Send email notification
        send_mail(
            subject=f"Your Order #{order.id} Status Updated",
            message=f"Hello {order.user.username},\n\nYour order status is now: {order.status}.",
            from_email=None,
            recipient_list=[order.user.email],
            fail_silently=False
        )

        return Response({"message": f"Order #{order.id} status updated to {order.status}"})

    return Response(serializer.errors, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    serializer = OrderSerializer(orders, many=True)
    return Response(serializer.data)


# Cancel Order API
@api_view(['POST'])
@permission_classes([IsAdminUser])
def cancel_order(request, order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=404)

    order.status = 'cancelled'
    order.save()

    return Response({"message": f"Order #{order.id} has been cancelled."})


# Coupon API
@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_coupon(request):
    serializer = CouponSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)


# This view is for retrieving a single coupon by its ID
@api_view(['GET'])
def list_active_coupons(request):
    coupons = Coupon.objects.filter(active=True)
    serializer = CouponSerializer(coupons, many=True)
    return Response(serializer.data)


#admin view to update tracking number
@api_view(['POST'])
@permission_classes([IsAdminUser])
def update_tracking_number(request, order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=404)

    tracking_number = request.data.get('tracking_number')
    if not tracking_number:
        return Response({"error": "Tracking number is required"}, status=400)

    order.tracking_number = tracking_number
    order.save()

    return Response({
        "message": f"Tracking number updated for Order #{order.id}",
        "tracking_number": order.tracking_number
    })


# This view is for creating a review for a product
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_review(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return Response({"error": "Product not found"}, status=404)

    data = request.data.copy()
    data['user'] = request.user.id
    data['product'] = product_id

    serializer = ReviewSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)

    return Response(serializer.errors, status=400)


@api_view(['GET'])
def product_reviews(request, product_id):
    reviews = Review.objects.filter(product_id=product_id).order_by('-created_at')
    serializer = ReviewSerializer(reviews, many=True)
    return Response(serializer.data)


# Generate a random tracking number
def generate_tracking_number():
    prefix = "UK-PF"
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"{prefix}-{random_part}"

@api_view(['POST'])
@permission_classes([IsAdminUser])
def update_order_status(request, order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=404)

    serializer = UpdateOrderStatusSerializer(data=request.data)
    if serializer.is_valid():
        order.status = serializer.validated_data['status']

        # ✅ Auto-generate tracking number if status is shipped and none exists
        if order.status == 'shipped' and not order.tracking_number:
            order.tracking_number = generate_tracking_number()

        order.save()

        # (keep your email notification here too)

        return Response({
            "message": f"Order #{order.id} status updated to {order.status}",
            "tracking_number": order.tracking_number
        })

    return Response(serializer.errors, status=400)

# delivery address model
# This is the API for the DeliveryAddress
# List + Create
class DeliveryAddressListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DeliveryAddressSerializer

    def get_queryset(self):
        return DeliveryAddress.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save(user=request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Failed to add address: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Retrieve, Update, Delete
class DeliveryAddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DeliveryAddressSerializer

    def get_queryset(self):
        return DeliveryAddress.objects.filter(user=self.request.user)

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)

            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Failed to update address: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.delete()
            return Response({"message": "Address deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"error": f"Failed to delete address: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# This is the API for the User Profile
class UserProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user
    

# List user refunds / Submit a refund request
class RefundRequestListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RefundRequestSerializer

    def get_queryset(self):
        return RefundRequest.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save(user=request.user)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Failed to submit refund request: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Admin: view and update refund status
class RefundRequestDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = RefundRequestSerializer
    queryset = RefundRequest.objects.all()

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)

            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response(
                {"error": f"Failed to update refund status: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# This is the API for Product Images

class ProductImageListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductImageSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return ProductImage.objects.all()

class ProductImageDeleteView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer