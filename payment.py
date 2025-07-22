from flask import Blueprint, request, jsonify
import stripe
import os
from datetime import datetime
import uuid

payment_bp = Blueprint('payment', __name__)

# Set your Stripe secret key (you'll need to replace this with your actual key)
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', 'sk_test_YOUR_SECRET_KEY_HERE')

# Stripe Price IDs for each plan (you'll need to create these in Stripe Dashboard)
STRIPE_PRICE_IDS = {
    'basic': 'price_YOUR_BASIC_PRICE_ID',
    'standard': 'price_YOUR_STANDARD_PRICE_ID', 
    'premium': 'price_YOUR_PREMIUM_PRICE_ID'
}

@payment_bp.route('/create-subscription', methods=['POST'])
def create_subscription():
    """Create a new Stripe subscription"""
    try:
        data = request.get_json()
        payment_method_id = data.get('payment_method_id')
        plan_name = data.get('plan_name', '').lower()
        
        if not payment_method_id:
            return jsonify({'error': 'Payment method is required'}), 400
        
        if plan_name not in STRIPE_PRICE_IDS:
            return jsonify({'error': 'Invalid plan selected'}), 400
        
        # Create customer
        customer = stripe.Customer.create(
            payment_method=payment_method_id,
            email=data.get('email', 'customer@example.com'),  # You should get this from user data
            invoice_settings={
                'default_payment_method': payment_method_id,
            },
        )
        
        # Create subscription
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{
                'price': STRIPE_PRICE_IDS[plan_name],
            }],
            expand=['latest_invoice.payment_intent'],
        )
        
        # Handle subscription status
        if subscription.status == 'active':
            # Subscription is active, update user in database
            # In a real app, you'd update the user's subscription status in your database
            return jsonify({
                'subscription_id': subscription.id,
                'customer_id': customer.id,
                'status': 'active',
                'plan': plan_name,
                'message': 'Subscription created successfully!'
            })
        elif subscription.status == 'incomplete':
            # Payment requires additional action
            payment_intent = subscription.latest_invoice.payment_intent
            return jsonify({
                'subscription_id': subscription.id,
                'customer_id': customer.id,
                'status': 'incomplete',
                'client_secret': payment_intent.client_secret,
                'message': 'Payment requires additional authentication'
            })
        else:
            return jsonify({'error': 'Subscription creation failed'}), 400
            
    except stripe.error.CardError as e:
        return jsonify({'error': f'Card error: {e.user_message}'}), 400
    except stripe.error.RateLimitError as e:
        return jsonify({'error': 'Too many requests. Please try again later.'}), 429
    except stripe.error.InvalidRequestError as e:
        return jsonify({'error': f'Invalid request: {str(e)}'}), 400
    except stripe.error.AuthenticationError as e:
        return jsonify({'error': 'Authentication failed. Please check your Stripe keys.'}), 401
    except stripe.error.APIConnectionError as e:
        return jsonify({'error': 'Network error. Please try again.'}), 502
    except stripe.error.StripeError as e:
        return jsonify({'error': f'Stripe error: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

@payment_bp.route('/cancel-subscription', methods=['POST'])
def cancel_subscription():
    """Cancel a Stripe subscription"""
    try:
        data = request.get_json()
        subscription_id = data.get('subscription_id')
        
        if not subscription_id:
            return jsonify({'error': 'Subscription ID is required'}), 400
        
        # Cancel the subscription
        subscription = stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True
        )
        
        return jsonify({
            'subscription_id': subscription.id,
            'status': subscription.status,
            'cancel_at_period_end': subscription.cancel_at_period_end,
            'current_period_end': subscription.current_period_end,
            'message': 'Subscription will be cancelled at the end of the current period'
        })
        
    except stripe.error.InvalidRequestError as e:
        return jsonify({'error': f'Invalid request: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@payment_bp.route('/subscription-status/<subscription_id>', methods=['GET'])
def get_subscription_status(subscription_id):
    """Get subscription status"""
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        
        return jsonify({
            'subscription_id': subscription.id,
            'status': subscription.status,
            'current_period_start': subscription.current_period_start,
            'current_period_end': subscription.current_period_end,
            'cancel_at_period_end': subscription.cancel_at_period_end,
            'plan': subscription.items.data[0].price.nickname if subscription.items.data else None
        })
        
    except stripe.error.InvalidRequestError as e:
        return jsonify({'error': f'Subscription not found: {str(e)}'}), 404
    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@payment_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks"""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET', 'whsec_YOUR_WEBHOOK_SECRET')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Handle the event
    if event['type'] == 'invoice.payment_succeeded':
        # Payment succeeded, update user subscription status
        invoice = event['data']['object']
        customer_id = invoice['customer']
        subscription_id = invoice['subscription']
        
        # Update user subscription in your database
        print(f"Payment succeeded for customer {customer_id}, subscription {subscription_id}")
        
    elif event['type'] == 'invoice.payment_failed':
        # Payment failed, handle accordingly
        invoice = event['data']['object']
        customer_id = invoice['customer']
        
        print(f"Payment failed for customer {customer_id}")
        
    elif event['type'] == 'customer.subscription.deleted':
        # Subscription cancelled, update user status
        subscription = event['data']['object']
        customer_id = subscription['customer']
        
        print(f"Subscription cancelled for customer {customer_id}")
    
    return jsonify({'status': 'success'})

@payment_bp.route('/plans', methods=['GET'])
def get_plans():
    """Get available subscription plans"""
    plans = [
        {
            'id': 'free',
            'name': 'Free',
            'price': 0,
            'pages': 200,
            'duration': '7 days',
            'features': ['Basic mistake detection', 'Grammar & spelling check', 'Limited language support'],
            'stripe_price_id': None
        },
        {
            'id': 'basic',
            'name': 'Basic',
            'price': 10,
            'pages': 1500,
            'duration': 'per month',
            'features': ['Advanced mistake detection', 'Multiple languages', 'Grammar & spelling check', 'Email support'],
            'stripe_price_id': STRIPE_PRICE_IDS['basic']
        },
        {
            'id': 'standard',
            'name': 'Standard',
            'price': 22,
            'pages': 5000,
            'mcq_analysis': 200,
            'duration': 'per month',
            'features': ['All Basic features', '200 MCQ analysis', 'Priority processing', 'Detailed reports', 'Phone support'],
            'stripe_price_id': STRIPE_PRICE_IDS['standard']
        },
        {
            'id': 'premium',
            'name': 'Premium',
            'price': 30,
            'pages': 10000,
            'mcq_analysis': 500,
            'duration': 'per month',
            'features': ['All Standard features', '500 MCQ analysis', 'Answer key comparison', 'Bulk processing', 'API access', '24/7 support'],
            'stripe_price_id': STRIPE_PRICE_IDS['premium']
        }
    ]
    
    return jsonify({'plans': plans})

