import os
import pandas as pd

# File where users are stored
USERS_FILE = "users.csv"

# Initialize users if the file doesn't exist or is empty
if not os.path.exists(USERS_FILE) or os.path.getsize(USERS_FILE) == 0:
    # Create an empty file with proper headers
    pd.DataFrame(columns=["Username", "Password", "Role"]).to_csv(USERS_FILE, index=False)

# List of users to add
users = [
    {'username': 'Selvaraju', 'password': '23121978', 'role': 'DAD'},
    {'username': 'Jeyakodi', 'password': '22051982', 'role': 'MOM'},
    {'username': 'Selvamathan', 'password': '30062006', 'role': 'SON'},
    {'username': 'Yashini', 'password': '18062008', 'role': 'DAUGHTER'}
]

# Read existing user data from the CSV
users_df = pd.read_csv(USERS_FILE)

# Add users if they don't exist
for user in users:
    # Check if the username already exists
    if user['username'] not in users_df["Username"].values:
        new_user = pd.DataFrame({"Username": [user['username']], 
                                 "Password": [user['password']], 
                                 "Role": [user['role']]})
        users_df = pd.concat([users_df, new_user], ignore_index=True)

# Save back to the CSV
users_df.to_csv(USERS_FILE, index=False)
print("Users added successfully!")
