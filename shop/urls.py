from django.urls import path
from .views import ProductListView, CategoryListView, CustomAuthToken, register, UserProfileView, checkout, order_history, OrderHistoryView, AdminOrderListView, sales_report, ProductDetailView, ProductUpdateDeleteView, restock_product, low_stock_products, update_order_status, cancel_order, update_tracking_number, create_coupon, DeliveryAddressListCreateView, DeliveryAddressDetailView, list_active_coupons, create_review, product_reviews, RefundRequestListCreateView, RefundRequestDetailView, ProductImageListCreateView, ProductImageDeleteView

urlpatterns = [
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/<int:id>/', ProductListView.as_view(), name='product-detail'),
    path('products/detail/<int:id>/', ProductDetailView.as_view(), name='product-detail'),
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('auth/register/', register, name='register'),
    path('auth/login/', CustomAuthToken.as_view(), name='login'),
    path('cart/checkout/', checkout, name='checkout'),
    path('orders/', OrderHistoryView.as_view(), name='order-history'),
    path('admin/orders/', AdminOrderListView.as_view(), name='admin-order-list'),
    path('admin/sales-report/', sales_report, name='sales-report'),
    path('products/update/<int:id>/', ProductUpdateDeleteView.as_view(), name='product-update-delete'),
    path('admin/restock/', restock_product, name='restock'),
    path('admin/low-stock/', low_stock_products, name='low-stock-products'),
    path('admin/update-order-status/<int:order_id>/', update_order_status, name='update-order-status'),
    path('admin/cancel-order/<int:order_id>/', cancel_order, name='cancel-order'),
    path('admin/update-tracking-number/<int:order_id>/', update_tracking_number, name='update-tracking-number'),
    path('admin/create-coupon/', create_coupon, name='create-coupon'),
    path('admin/list-active-coupons/', list_active_coupons, name='list-active-coupons'),
    path('products/<int:product_id>/reviews/', create_review, name='create-review'),
    path('products/<int:product_id>/reviews/list/', product_reviews, name='product-reviews'),
    path('orders/history/', order_history, name='order-history'),
    path('delivery-addresses/', DeliveryAddressListCreateView.as_view(), name='delivery-address-list-create'),
    path('delivery-addresses/<int:pk>/', DeliveryAddressDetailView.as_view(), name='delivery-address-detail'),
    path('user/profile/', UserProfileView.as_view(), name='user-profile'),
    path('refund-requests/', RefundRequestListCreateView.as_view(), name='refund-request-list-create'),
    path('refund-requests/<int:pk>/', RefundRequestDetailView.as_view(), name='refund-request-detail'),
    path('products/<int:product_id>/images/', ProductImageListCreateView.as_view(), name='product-image-list-create'),
    path('products/images/<int:pk>/', ProductImageDeleteView.as_view(), name='product-image-delete'),

]