from flask import Flask, request, render_template, redirect, session, url_for, jsonify
import pandas as pd
import os
from flask import send_from_directory

app = Flask(__name__)
app.secret_key = "supersecretkey"

csv_file = "users.xlsx"
recipe_file = "Cleaned_Indian_Food_Dataset.csv"
uploads_folder = "uploads"
posts_file = "posts.csv"


import pandas as pd

posts = pd.read_csv("posts.csv").fillna("")  # Replace NaN with empty string

# Ensure Comments and Liked_By are strings
posts["Comments"] = posts["Comments"].astype(str)
posts["Liked_By"] = posts["Liked_By"].astype(str)

import pandas as pd

# Load users.xlsx
users = pd.read_excel("users.xlsx").fillna("")

# Add Followers and Following columns if they don't exist
if "Followers" not in users.columns:
    users["Followers"] = ""

if "Following" not in users.columns:
    users["Following"] = ""

# Save changes
users.to_excel("users.xlsx", index=False)
print("Updated users.xlsx with Followers and Following columns.")


import os

UPLOAD_FOLDER = "profile_pics"  # Folder to store profile pictures

# Ensure the folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)




# Ensure necessary files and folders exist
os.makedirs(uploads_folder, exist_ok=True)

if not os.path.exists(csv_file):
    pd.DataFrame(columns=["Name", "Username", "Password"]).to_excel(csv_file, index=False)

if not os.path.exists(posts_file):
    pd.DataFrame(columns=["Username", "Image_Path", "Description"]).to_csv(posts_file, index=False)

df = pd.read_csv(recipe_file)



def recommend_recipes(entered_ingredients, top_n=5):
    entered_ingredients = {i.strip().lower() for i in entered_ingredients.split(",")}
    matching_recipes = []
    for _, row in df.iterrows():
        recipe_ingredients = {i.strip().lower() for i in row["Cleaned-Ingredients"].split(",")}
        match_count = len(entered_ingredients & recipe_ingredients)
        if match_count > 1:
            matching_recipes.append((match_count, row.to_dict()))
    matching_recipes.sort(reverse=True, key=lambda x: x[0])
    return [recipe[1] for recipe in matching_recipes[:top_n]]



@app.route("/index", methods=["GET", "POST"])  # Allow both GET and POST
def index():
    if "user" not in session:
        return redirect("/login")
    recipes = []
    if request.method == "POST":
        user_input = request.form.get("ingredients", "")
        if user_input:
            recipes = recommend_recipes(user_input)
    return render_template("index.html", recipes=recipes)



@app.route("/search_by_recipe")
def search_by_recipe():
    query = request.args.get("query", "").strip().lower()
    
    if not query:
        return jsonify([])

    if "TranslatedRecipeName" not in df.columns:
        return jsonify({"error": "Recipe column missing"})

    filtered_df = df[df["TranslatedRecipeName"].str.lower().str.contains(query, na=False, regex=False)]

    return jsonify(filtered_df.head(5).to_dict(orient="records"))


@app.route("/search_by_ingredients")
def search_by_ingredients():
    ingredients = request.args.get("ingredients", "").strip().lower().split(",")

    if not ingredients or not any(ingredients):
        return jsonify([])

    ingredients = {i.strip() for i in ingredients}

    matching_recipes = []
    for _, row in df.iterrows():
        recipe_ingredients = {i.strip().lower() for i in row.get("Cleaned-Ingredients", "").split(",")}
        match_count = len(ingredients & recipe_ingredients)
        if match_count > 1:
            matching_recipes.append((match_count, row.to_dict()))

    matching_recipes.sort(reverse=True, key=lambda x: x[0])

    return jsonify([recipe[1] for recipe in matching_recipes[:5]])




@app.route("/")
def home():
    return redirect("/login")



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        users = pd.read_excel(csv_file, dtype=str)
        users["Username"] = users["Username"].astype(str).str.strip()
        users["Password"] = users["Password"].astype(str).str.strip()

        matching_user = users[(users["Username"] == username) & (users["Password"] == password)]

        if not matching_user.empty:
            session["user"] = username
            return redirect("/dashboard")  # Redirect to dashboard after login
        else:
            return "Invalid username or password. Try again."

    return render_template("login.html")



@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"].strip()
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        # Load existing users
        users = pd.read_excel(csv_file, dtype=str)

        # Check if username already exists
        if username in users["Username"].values:
            return "Username already exists. Choose another one."

        # Add new user to DataFrame
        new_user = pd.DataFrame([[name, username, password]], columns=["Name", "Username", "Password"])
        users = pd.concat([users, new_user], ignore_index=True)

        # Save back to Excel
        users.to_excel(csv_file, index=False)

        return redirect("/login")  # Redirect to login after successful signup

    return render_template("signup.html")




@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")




@app.route("/dashboard", methods=["GET"])
def dashboard():
    if "user" not in session:
        return redirect("/login")

    username = session.get("user")  # Logged-in user
    profile_username = request.args.get("username", username)  # Viewing profile

    # Load user details
    users = pd.read_excel("users.xlsx").fillna("")
    user_data = users[users["Username"] == profile_username].iloc[0]
    profile_pic = str(user_data.get("Profile_Pic_Path", ""))

    # Load posts
    posts = pd.read_csv(posts_file).fillna("").to_dict(orient="records")

    # Load user profile pictures from users.xlsx
    users_df = pd.read_excel(users_file)

    # Map usernames to their profile picture paths
    user_pics = dict(zip(users_df["Username"], users_df.get("Profile_Pic_Path", ""))) if "Profile_Pic_Path" in users_df.columns else {}

    return render_template("dashboard.html", posts=posts, user_pics=user_pics)




@app.route("/share", methods=["GET", "POST"])
def share():
    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":
        if "image" not in request.files:
            return "No file uploaded."

        file = request.files["image"]
        description = request.form.get("description", "").strip()

        if file.filename == "":
            return "No selected file."

        # Save the image
        filename = file.filename  
        file.save(os.path.join(uploads_folder, filename))

        # Load existing posts
        posts = pd.read_csv(posts_file)

        # Add new post
        new_post = pd.DataFrame([[session["user"], filename, description, 0, "", ""]], 
                                columns=["Username", "Image_Path", "Description", "Likes", "Liked_By", "Comments"])
        posts = pd.concat([posts, new_post], ignore_index=True)
        posts.to_csv(posts_file, index=False)

        return redirect("/dashboard")

    return render_template("share.html")  # Renders the new share page




@app.route("/like/<filename>", methods=["POST"])
def like_post(filename):
    print(f"🔥 Like request received for: {filename}")
    print(f"User: {session.get('user')}")  # Print current user

    posts = pd.read_csv(posts_file).fillna("")

    row_index = posts.index[posts["Image_Path"] == filename].tolist()
    if not row_index:
        print("❌ Post not found")
        return "Post not found", 404

    row_index = row_index[0]
    liked_by = str(posts.at[row_index, "Liked_By"])
    liked_by_list = liked_by.split('|') if liked_by else []

    # ✅ Prevent duplicate likes (Ignore if already liked)
    if session["user"] in liked_by_list:
        print("⚠️ User has already liked this post. Ignoring...")
        return "Success"  # Just return "Success" without updating the count

    # Add like
    liked_by_list.append(session["user"])
    posts.at[row_index, "Likes"] = len(liked_by_list)
    posts.at[row_index, "Liked_By"] = '|'.join(liked_by_list)
    posts.to_csv(posts_file, index=False)

    print(f"✅ Likes updated: {posts.at[row_index, 'Likes']}")
    print(f"Liked By: {posts.at[row_index, 'Liked_By']}")

    return "Success"

@app.route("/get_likes/<filename>")
def get_likes(filename):
    posts = pd.read_csv(posts_file).fillna("")
    row_index = posts.index[posts["Image_Path"] == filename].tolist()
    
    if not row_index:
        return {"likes": 0}  # Default to 0 if post not found
    
    row_index = row_index[0]
    return {"likes": int(posts.at[row_index, "Likes"])}



@app.route("/comment/<filename>", methods=["POST"])
def comment_post(filename):
    posts = pd.read_csv(posts_file).fillna("")

    data = request.get_json()
    comment_text = data.get("comment", "").strip()

    # Check if the post exists
    row_index = posts.index[posts["Image_Path"] == filename].tolist()
    if not row_index:
        return "Post not found", 404
    
    row_index = row_index[0]

    # Get existing comments
    comments = str(posts.at[row_index, "Comments"])
    comments_list = comments.split('|') if isinstance(comments, str) and comments else []

    # Add new comment
    comments_list.append(f"{session['user']}: {comment_text}")
    posts.at[row_index, "Comments"] = '|'.join(comments_list)

    # Save back to CSV
    posts.to_csv(posts_file, index=False)

    return "Success"



@app.route('/delete/<filename>', methods=['POST'])
def delete_post(filename):
    if "user" not in session:
        return "Unauthorized", 403

    username = session["user"]
    posts = pd.read_csv(posts_file)

    post_index = posts[(posts["Image_Path"] == filename) & (posts["Username"] == username)].index

    if len(post_index) == 0:
        return "Unauthorized", 403

    posts.drop(post_index, inplace=True)
    posts.to_csv(posts_file, index=False)

    return "Success", 200




@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(uploads_folder, filename)


@app.route("/add_recipe", methods=["GET", "POST"])
def add_recipe():
    if "user" not in session:
        return redirect("/login")
    if request.method == "POST":
        new_recipe = {
            "TranslatedRecipeName": request.form["TranslatedRecipeName"],
            "TranslatedIngredients": request.form["TranslatedIngredients"],
            "TotalTimeInMins": request.form["TotalTimeInMins"],
            "Cuisine": request.form["Cuisine"],
            "TranslatedInstructions": request.form["TranslatedInstructions"],
            "URL": request.form["URL"],
            "Cleaned-Ingredients": request.form["Cleaned-Ingredients"],
            "image-url": request.form["image-url"],
            "Ingredient-count": request.form["Ingredient-count"]
        }
        df = pd.read_csv(recipe_file)
        df = pd.concat([df, pd.DataFrame([new_recipe])], ignore_index=True)
        df.to_csv(recipe_file, index=False)
        return redirect("/index")
    return render_template("add_recipe.html")


users_file="users.xlsx"

import pandas as pd

import pandas as pd

from flask import session, request, redirect, url_for

@app.route("/profile")
def profile():
    username = session.get("user")  # Logged-in user
    profile_username = request.args.get("username", username)  # Viewing profile

    if not username:
        return redirect(url_for("login"))  # Ensure user is logged in

    users = pd.read_excel("users.xlsx").fillna("")
    users_df = pd.read_excel(users_file)

# Ensure Profile_Pic_Path column exists and map usernames to profile pic paths
    if "Profile_Pic_Path" in users_df.columns:
        user_pics = dict(zip(users_df["Username"], users_df["Profile_Pic_Path"]))  
    else:
        user_pics = {}  # No profile picture data


    
    
    if profile_username not in users["Username"].values:
        return "User not found", 404

    user_data = users[users["Username"] == profile_username].iloc[0]
    
    profile_pic = str(user_data.get("Profile_Pic_Path", ""))
    email = user_data.get("EmailID", "Not Provided")

    followers = user_data.get("Followers", "").split(",") if user_data.get("Followers") else []
    following = user_data.get("Following", "").split(",") if user_data.get("Following") else []

    is_following = username in followers

    posts = pd.read_csv("posts.csv")
    user_posts = posts[posts["Username"] == profile_username].to_dict(orient="records")

    return render_template("profile.html",
                           name=user_data["Name"],
                           username=profile_username,
                           email=email,
                           profile_pic=profile_pic,
                           followers=len(followers),
                           following=len(following),
                           is_following=is_following,
                           user_posts=user_posts,
                           session=session)  # Pass session explicitly



@app.route("/follow", methods=["POST"])
def follow_user():
    logged_in_user = session.get("user")
    profile_username = request.form.get("username")  # The user being followed

    if not logged_in_user or not profile_username:
        return redirect(url_for("profile", username=profile_username))

    # Load users data
    users = pd.read_excel("users.xlsx").fillna("")

    # Get user data
    profile_index = users[users["Username"] == profile_username].index[0]
    logged_in_index = users[users["Username"] == logged_in_user].index[0]

    # Followers list of the profile user
    profile_followers = users.at[profile_index, "Followers"].split(",") if users.at[profile_index, "Followers"] else []
    
    # Following list of logged-in user
    logged_in_following = users.at[logged_in_index, "Following"].split(",") if users.at[logged_in_index, "Following"] else []

    if logged_in_user in profile_followers:
        # Unfollow: Remove from both lists
        profile_followers.remove(logged_in_user)
        logged_in_following.remove(profile_username)
    else:
        # Follow: Add to both lists
        profile_followers.append(logged_in_user)
        logged_in_following.append(profile_username)

    # Save updated values
    users.at[profile_index, "Followers"] = ",".join(profile_followers)
    users.at[logged_in_index, "Following"] = ",".join(logged_in_following)
    users.to_excel("users.xlsx", index=False)

    return redirect(url_for("profile", username=profile_username))





@app.route("/edit_profile", methods=["POST"])
def edit_profile():
    if "user" not in session:
        return redirect(url_for("login"))

    new_username = request.form["new_username"]
    new_email = request.form["new_email"]

    user_data = pd.read_csv(users_file)
    user_data.loc[user_data["Username"] == session["user"], ["Username", "Email"]] = [new_username, new_email]
    user_data.to_csv(users_file, index=False)

    session["user"] = new_username  # Update session
    return redirect(url_for("profile"))



@app.route("/edit_bio", methods=["POST"])
def edit_bio():
    if "user" not in session:
        return redirect(url_for("login"))

    new_bio = request.form["bio"]

    user_data = pd.read_csv(users_file)
    user_data.loc[user_data["Username"] == session["user"], "Bio"] = new_bio
    user_data.to_csv(users_file, index=False)

    return redirect(url_for("profile"))


@app.route("/update_email", methods=["POST"])
def update_email():
    if "user" not in session:
        return redirect("/login")

    username = session["user"]
    email = request.form["email"]

    users_df = pd.read_excel("users.xlsx")
    users_df.loc[users_df["Username"] == username, "EmailID"] = email
    users_df.to_excel("users.xlsx", index=False)

    return redirect("/profile")


@app.route("/upload_profile_pic", methods=["POST"])
def upload_profile_pic():
    if "user" not in session:
        return redirect("/login")

    username = session["user"]
    if "profile_pic" not in request.files:
        return redirect("/profile")

    file = request.files["profile_pic"]
    if file.filename == "":
        return redirect("/profile")

    # Save profile picture
    filename = f"{username}.png"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    # Update profile picture path in users.xlsx
    users_df = pd.read_excel("users.xlsx")
    users_df.loc[users_df["Username"] == username, "Profile_Pic_Path"] = filepath
    users_df.to_excel("users.xlsx", index=False)

    return redirect("/profile")



from flask import send_from_directory

@app.route('/profile_pics/<filename>')
def uploaded_profile(filename):
    return send_from_directory("profile_pics", filename)


@app.route("/profile_pic/<username>")
def get_profile_pic(username):
    users = pd.read_excel("users.xlsx").fillna("")
    
    if username not in users["Username"].values:
        return redirect(url_for("static", filename="default_profile_pic.jpg"))

    user_data = users[users["Username"] == username].iloc[0]
    profile_pic = str(user_data.get("Profile_Pic_Path", ""))

    if profile_pic and os.path.exists(os.path.join("uploads", profile_pic.split("/")[-1])):
        return send_from_directory("uploads", profile_pic.split("/")[-1])  # Serve the actual profile pic
    
    return redirect(url_for("static", filename="default_profile_pic.jpg"))  # Default pic if empty


@app.route("/get-username")
def get_username():
    return {"username": session.get("user", "Guest")}

if __name__ == "__main__":
    app.run(debug=True)





