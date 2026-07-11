import psycopg2
from werkzeug.security import generate_password_hash
import random
from datetime import datetime, timedelta

# Your Supabase connection string
DATABASE_URL = "postgresql://postgres.zksoqgvptnbraxlmwvgn:Shareplate%4006@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"

def get_db():
    return psycopg2.connect(DATABASE_URL)

# Demo Users
users = [
    ("Rahul Sharma", "rahul@gmail.com", "password123", "Koramangala, Bengaluru", "donor"),
    ("Priya Patel", "priya@gmail.com", "password123", "Indiranagar, Bengaluru", "both"),
    ("Amit Kumar", "amit@gmail.com", "password123", "HSR Layout, Bengaluru", "donor"),
    ("Sneha Reddy", "sneha@gmail.com", "password123", "Whitefield, Bengaluru", "both"),
    ("Vijay Nair", "vijay@gmail.com", "password123", "JP Nagar, Bengaluru", "donor"),
    ("Ananya Singh", "ananya@gmail.com", "password123", "Jayanagar, Bengaluru", "receiver"),
    ("Kiran Rao", "kiran@gmail.com", "password123", "BTM Layout, Bengaluru", "both"),
    ("Deepa Menon", "deepa@gmail.com", "password123", "Marathahalli, Bengaluru", "donor"),
    ("Suresh Babu", "suresh@gmail.com", "password123", "Electronic City, Bengaluru", "both"),
    ("Lakshmi Iyer", "lakshmi@gmail.com", "password123", "Malleswaram, Bengaluru", "donor"),
]

# Demo Food listings
foods = [
    ("Vegetable Biryani", "Cooked Meal", "10 plates", "Koramangala 5th Block, Bengaluru", "Fresh biryani from house party", "9876543210"),
    ("Fresh Idli & Sambar", "Cooked Meal", "20 pieces", "Indiranagar 12th Main, Bengaluru", "Morning breakfast leftover", "9845678901"),
    ("Banana Bunch", "Fruits & Vegetables", "2 dozen", "HSR Layout Sector 2, Bengaluru", "Fresh bananas from function", "9812345678"),
    ("Bread Loaves", "Bakery", "5 loaves", "Whitefield Main Road, Bengaluru", "Freshly baked bread", "9898765432"),
    ("Chicken Curry & Rice", "Cooked Meal", "8 portions", "JP Nagar 7th Phase, Bengaluru", "Wedding leftover food", "9765432198"),
    ("Mixed Vegetables", "Fruits & Vegetables", "3 kg", "Jayanagar 4th Block, Bengaluru", "Fresh market vegetables", "9754321987"),
    ("Samosas & Chutney", "Snacks", "50 pieces", "BTM Layout 2nd Stage, Bengaluru", "Office party leftovers", "9743219876"),
    ("Fresh Orange Juice", "Beverages", "10 liters", "Marathahalli Bridge, Bengaluru", "Freshly squeezed juice", "9732198765"),
    ("Dal & Chapati", "Cooked Meal", "15 servings", "Electronic City Phase 1, Bengaluru", "Temple prasad food", "9721987654"),
    ("Fruit Cake", "Bakery", "3 cakes", "Malleswaram 15th Cross, Bengaluru", "Birthday party leftover", "9710987654"),
    ("Pulao Rice", "Cooked Meal", "12 plates", "Koramangala 3rd Block, Bengaluru", "Corporate lunch leftover", "9876543211"),
    ("Fresh Tomatoes", "Fruits & Vegetables", "5 kg", "Indiranagar 100 Feet Road, Bengaluru", "Farm fresh tomatoes", "9845678902"),
    ("Cookies & Biscuits", "Snacks", "4 packets", "HSR Layout BDA Complex, Bengaluru", "Unopened snack packets", "9812345679"),
    ("Lemon Rice", "Cooked Meal", "8 boxes", "Whitefield Hope Farm, Bengaluru", "Homemade lemon rice", "9898765433"),
    ("Fresh Milk", "Beverages", "5 liters", "JP Nagar 6th Phase, Bengaluru", "Extra milk from farm", "9765432199"),
]

reviews = [
    "Amazing food! Very fresh and tasty. Highly recommend!",
    "Great initiative! Food was still warm when I picked it up.",
    "Very generous donor. Will definitely use this app again!",
    "Food quality was excellent. Thank you for sharing!",
    "Quick pickup, very helpful. Great experience overall.",
    "Wonderful app and wonderful people. Food was delicious!",
    "So happy to find this app. Food was perfect!",
    "Donor was very kind and helpful. 5 stars!",
]

def add_demo_data():
    conn = get_db()
    c = conn.cursor()

    print("Adding demo users...")
    user_ids = []
    for name, email, password, location, role in users:
        try:
            hashed = generate_password_hash(password)
            c.execute(
                '''INSERT INTO users (name, email, password, location, role, security_answer)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (email) DO NOTHING RETURNING id''',
                (name, email, hashed, location, role, "demo")
            )
            result = c.fetchone()
            if result:
                user_ids.append(result[0])
                print(f"  ✅ Added user: {name}")
            else:
                c.execute('SELECT id FROM users WHERE email=%s', (email,))
                user_ids.append(c.fetchone()[0])
                print(f"  ⚠️ User already exists: {name}")
        except Exception as e:
            print(f"  ❌ Error adding {name}: {e}")

    conn.commit()

    print("\nAdding demo food listings...")
    food_ids = []
    for i, (name, category, quantity, location, notes, contact) in enumerate(foods):
        try:
            donor_id = user_ids[i % len(user_ids)]
            expiry = (datetime.now() + timedelta(hours=random.randint(2, 24))).strftime('%Y-%m-%d %H:%M')
            c.execute(
                '''INSERT INTO food (food_name, category, quantity, location, expiry, contact, notes, donor_id, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''',
                (name, category, quantity, location, expiry, contact, notes, donor_id, 'available')
            )
            food_id = c.fetchone()[0]
            food_ids.append(food_id)
            print(f"  ✅ Added food: {name}")
        except Exception as e:
            print(f"  ❌ Error adding {name}: {e}")

    conn.commit()

    print("\nAdding demo ratings...")
    for food_id in food_ids[:8]:
        try:
            reviewer_id = user_ids[random.randint(0, len(user_ids)-1)]
            rating = random.randint(3, 5)
            review = random.choice(reviews)
            c.execute(
                '''INSERT INTO ratings (food_id, user_id, rating, review)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT DO NOTHING''',
                (food_id, reviewer_id, rating, review)
            )
            print(f"  ✅ Added rating for food {food_id}")
        except Exception as e:
            print(f"  ❌ Error adding rating: {e}")

    conn.commit()
    conn.close()

    print("\n🎉 Demo data added successfully!")
    print(f"  👥 {len(users)} users added")
    print(f"  🍱 {len(foods)} food listings added")
    print(f"  ⭐ Ratings added")
    print("\nLogin with any demo account:")
    print("  Email: rahul@gmail.com")
    print("  Password: password123")

if __name__ == '__main__':
    add_demo_data()