import hashlib
import urllib.parse
import requests
import logging
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)

class PayFastService:
    """Service for generating PayFast payment forms and validating signatures"""
    
    PAYFAST_VALID_HOSTS = [
        'www.payfast.co.za',
        'sandbox.payfast.co.za',
        'w1w.payfast.co.za',
        'w2w.payfast.co.za',
    ]
    
    @staticmethod
    def generate_signature(data_dict, passphrase=None):
        """
        Generate MD5 signature for PayFast payment
        
        Args:
            data_dict: Dictionary of payment parameters
            passphrase: Optional passphrase for added security
        
        Returns:
            MD5 signature string
        """
        if passphrase is None:
            passphrase = settings.PAYFAST_PASSPHRASE
        
        payload_string = ""
        for key in sorted(data_dict.keys()):
            if key != 'signature' and data_dict[key]:
                payload_string += f"{key}={urllib.parse.quote_plus(str(data_dict[key]))}&"
        
        payload_string = payload_string.rstrip('&')
        
        if passphrase:
            payload_string += f"&passphrase={urllib.parse.quote_plus(passphrase)}"
        
        signature = hashlib.md5(payload_string.encode()).hexdigest()
        return signature
    
    @staticmethod
    def generate_payment_form_data(user, plan, subscription=None):
        """
        Generate PayFast payment form data for a subscription
        
        Args:
            user: Django User object
            plan: SubscriptionPlan object
            subscription: UserSubscription object (optional)
        
        Returns:
            Dictionary of payment form fields
        """
        payment_data = {
            'merchant_id': settings.PAYFAST_MERCHANT_ID,
            'merchant_key': settings.PAYFAST_MERCHANT_KEY,
            'return_url': f"{settings.SITE_URL}{reverse('payment_success')}",
            'cancel_url': f"{settings.SITE_URL}{reverse('payment_cancelled')}",
            'notify_url': f"{settings.SITE_URL}{reverse('payfast_notify')}",
            
            'name_first': user.first_name or user.username,
            'name_last': user.last_name or '',
            'email_address': user.email,
            
            'amount': str(plan.price),
            'item_name': f'{plan.name} Subscription',
            'item_description': plan.description,
            
            'custom_str1': str(user.id),
            'custom_str2': str(plan.id),
            'custom_str3': str(subscription.id) if subscription else '',
            
            'subscription_type': '1' if plan.price > 0 else '0',
            'billing_date': '',
            'recurring_amount': str(plan.price),
            'frequency': '3',
            'cycles': '0',
        }
        
        payment_data['signature'] = PayFastService.generate_signature(payment_data)
        
        return payment_data
    
    @staticmethod
    def validate_itn_signature(post_data):
        """
        Validate PayFast ITN (Instant Transaction Notification) signature
        
        Args:
            post_data: POST data from PayFast ITN request
        
        Returns:
            Boolean indicating if signature is valid
        """
        data_dict = {}
        for key, value in post_data.items():
            if key != 'signature':
                if isinstance(value, list):
                    data_dict[key] = value[0]
                else:
                    data_dict[key] = value
        
        received_signature = post_data.get('signature', [''])[0] if isinstance(post_data.get('signature'), list) else post_data.get('signature', '')
        
        calculated_signature = PayFastService.generate_signature(data_dict)
        
        return received_signature == calculated_signature
    
    @staticmethod
    def verify_payment_with_payfast(post_data):
        """
        Verify payment notification with PayFast servers (server-to-server validation)
        This is CRITICAL for security to prevent spoofed payment notifications
        
        Args:
            post_data: POST data from PayFast ITN request
        
        Returns:
            Boolean indicating if payment is valid
        """
        try:
            param_string = urllib.parse.urlencode(post_data)
            
            response = requests.post(
                settings.PAYFAST_VALIDATE_URL,
                data=param_string,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10
            )
            
            if response.status_code == 200 and response.text == 'VALID':
                logger.info('PayFast server validation: VALID')
                return True
            else:
                logger.error(f'PayFast server validation failed: {response.status_code} - {response.text}')
                return False
                
        except requests.RequestException as e:
            logger.error(f'Error connecting to PayFast validation server: {str(e)}')
            return False
    
    @staticmethod
    def validate_payment_amount(post_data, expected_amount):
        """
        Validate that the payment amount matches the expected amount
        
        Args:
            post_data: POST data from PayFast
            expected_amount: Expected payment amount
        
        Returns:
            Boolean indicating if amounts match
        """
        try:
            received_amount = float(post_data.get('amount_gross', 0))
            expected_amount = float(expected_amount)
            
            return abs(received_amount - expected_amount) < 0.01
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_merchant_id(post_data):
        """
        Validate that the merchant ID matches our configuration
        
        Args:
            post_data: POST data from PayFast
        
        Returns:
            Boolean indicating if merchant ID is valid
        """
        received_merchant_id = post_data.get('merchant_id', '')
        return received_merchant_id == settings.PAYFAST_MERCHANT_ID
    
    @staticmethod
    def get_payfast_url():
        """Get the appropriate PayFast payment URL (sandbox or production)"""
        return settings.PAYFAST_URL
