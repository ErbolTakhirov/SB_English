
import os
import django
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sb_finance.settings')
django.setup()

from django.contrib.auth import get_user_model
from core.ai.advisor import get_financial_advice

def test_off_topic():
    User = get_user_model()
    # Ensure there is at least one user
    if not User.objects.exists():
        print("Creating dummy user for test...")
        user = User.objects.create_user(username='testuser', password='password')
    else:
        user = User.objects.first()
    
    print(f"Testing with user: {user.username}")

    # 1. Off-topic query
    off_topic_query = "Какая сегодня погода в Токио?"
    print(f"\n--- Testing Off-Topic Query: '{off_topic_query}' ---")
    result_off = get_financial_advice(user, off_topic_query)
    print("Response:")
    print(result_off['response'])

    # 2. Another off-topic query
    off_topic_query_2 = "Как приготовить борщ?"
    print(f"\n--- Testing Off-Topic Query: '{off_topic_query_2}' ---")
    result_off_2 = get_financial_advice(user, off_topic_query_2)
    print("Response:")
    print(result_off_2['response'])

    # 3. Relevant query
    relevant_query = "Как мне оптимизировать свои расходы на еду?"
    print(f"\n--- Testing Relevant Query: '{relevant_query}' ---")
    result_rel = get_financial_advice(user, relevant_query)
    print("Response:")
    # We don't want to print full response if it's long, just the beginning
    print(result_rel['response'][:200] + "...")

if __name__ == "__main__":
    test_off_topic()
