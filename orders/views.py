from django.core.mail import EmailMessage
from django.shortcuts import render, redirect
from django.template.loader import render_to_string

from carts.models import CartItem
from store.models import Product
from .forms import OrderForm
from .models import Order, Payment, OrderProduct
import datetime


def payments(request):
    order = Order.objects.get(user=request.user, is_ordered=False)
    order.is_ordered = True
    order.save()
    return render(request, 'orders/payments.html')


def cash_on_delivery(request):
    order = Order.objects.get(user=request.user, is_ordered=False)
    order.is_ordered = True
    order.save()

    # move cart to order products
    cart_items = CartItem.objects.filter(user=request.user)
    for item in cart_items:
        orderproduct = OrderProduct()
        orderproduct.order_id = order.id
        orderproduct.user_id = request.user.id
        orderproduct.product_id = item.product_id
        orderproduct.quantity = item.quantity
        orderproduct.product_price = item.product.price
        orderproduct.ordered = True
        orderproduct.save()

        cart_item = CartItem.objects.get(id=item.id)
        product_variation = cart_item.variations.all()
        orderproduct = OrderProduct.objects.get(id=orderproduct.id)
        orderproduct.variations.set(product_variation)
        orderproduct.save()

        # Reduce quantity of sold product
        product = Product.objects.get(id=item.product_id)
        product.stock -= item.quantity
        product.save()

    # clear cart
    CartItem.objects.filter(user=request.user).delete()

    # send email to customer
    mail_subject = 'Thank you for your order!'
    message = render_to_string('orders/order_received_email.html', {
        'user': request.user,
        'order': order,
    })
    to_email = request.user.email
    send_email = EmailMessage(mail_subject, message, to=[to_email])
    send_email.send()

    # send order number and transaction id back to sendData method Json Response
    redirect_url = ''
    return redirect('order_complete/?order_number='+order.order_number)
    # return render(request, 'orders/order_complete.html')


def place_order(request, total=0, quantity=0):
    current_user = request.user

    # if cart is null then return to store
    cart_items = CartItem.objects.filter(user=current_user)
    cart_count = cart_items.count()
    if cart_count <= 0:
        return redirect('store')
    grand_total = 0
    tax = 0
    for cart_item in cart_items:
        total += (cart_item.product.price * cart_item.quantity)
        quantity += cart_item.quantity

    grand_total = total + tax

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            data = Order()
            data.user = current_user
            data.first_name = form.cleaned_data['first_name']
            data.last_name = form.cleaned_data['last_name']
            data.phone = form.cleaned_data['phone']
            data.email = form.cleaned_data['email']
            data.address_line_1 = form.cleaned_data['address_line_1']
            data.address_line_2 = form.cleaned_data['address_line_2']
            data.postcode = form.cleaned_data['postcode']
            data.country = 'United Kingdom'  # form.cleaned_data['country']
            data.state = form.cleaned_data['state']
            data.city = form.cleaned_data['city']
            data.order_note = form.cleaned_data['order_note']
            data.order_total = grand_total
            data.tax = tax
            data.ip = request.META.get('REMOTE_ADDR')
            data.save()
            # Generate order number
            yr = int(datetime.date.today().strftime('%Y'))
            dt = int(datetime.date.today().strftime('%d'))
            mt = int(datetime.date.today().strftime('%m'))
            d = datetime.date(yr, mt, dt)
            current_date = d.strftime("%Y%m%d")
            order_number = current_date + str(data.id)
            data.order_number = order_number
            data.save()

            order = Order.objects.get(user=current_user, is_ordered=False, order_number=order_number)
            context = {
                'order': order,
                'full_name': data.full_name(),
                'full_address': data.full_address(),
                'postcode': data.postcode,
                'state': data.state,
                'city': data.city,
                'order_note': data.order_note,
                'country': data.country,
                'phone': data.phone,
                'email': data.email,
                'order_number': order_number,
                'cart_items': cart_items,
                'total': total,
                'grand_total': grand_total,

            }

            return render(request, 'orders/payments.html', context)
    else:
        return redirect('checkout')


def order_complete(request):
    order_number = request.GET.get('order_number')

    try:
        order = Order.objects.get(order_number=order_number, is_ordered=True)
        ordered_products = OrderProduct.objects.filter(order_id=order.id)

        subtotal = 0
        for i in ordered_products:
            subtotal += i.product_price * i.quantity

        context = {
            'order': order,
            'order_number': order_number,
            'ordered_products': ordered_products,
            'subtotal': subtotal,


        }
        return render(request, 'orders/order_complete.html', context)
    except(Order.DoesNotExist):
        return redirect('home')



    return render(request, 'orders/cash_on_delivery/order_complete.html')
