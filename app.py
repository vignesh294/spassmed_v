# Python standard libraries
import json
import os
from os import listdir, mkdir
from os.path import isfile, join
import sqlite3
import sys


# Third party libraries
from flask import Flask, redirect, request, url_for, render_template
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from oauthlib.oauth2 import WebApplicationClient
import requests

# Internal imports
from db import init_db_command
from user import User

# Configuration
GOOGLE_CLIENT_ID = "981631304774-al2bm630eqralacp6hrpd9esapc5gnq3.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)

# Flask app setup
app = Flask(__name__) #, static_folder='\/static')
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)

# User session management setup
# https://flask-login.readthedocs.io/en/latest
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.unauthorized_handler
def unauthorized():
    return "You must be logged in to access this content.", 403


# Naive database setup
try:
    init_db_command()
except sqlite3.OperationalError:
    # Assume it's already been created
    pass

# OAuth2 client setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)


images_with_csv_entries = []
images_without_csv_entries = []
selected_project_name = None
project_has_csv = False


# Flask-Login helper to retrieve a user from our db
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


@app.route("/")
def index():
    if current_user.is_authenticated:
        # retrieve the user's images
        return render_template("index3.html", name=current_user.name, email=current_user.email, profile_pic=current_user.profile_pic, images_with_csv_entries = images_with_csv_entries, images_without_csv_entries = images_without_csv_entries, projects = get_projects(), project_has_csv = project_has_csv)
        """
        return (
            "<p>Hello, {}! You're logged in! Email: {}</p>"
            "<div><p>Google Profile Picture:</p>"
            '<img src="{}" alt="Google profile pic"></img></div>'
            '<a class="button" href="/logout">Logout</a>' 
            '<iframe width="402" height="346" frameborder="0" scrolling="no" src="https://queensuca-my.sharepoint.com/personal/20vr1_queensu_ca/_layouts/15/Doc.aspx?sourcedoc={d4aec8fa-8909-4dfc-8ec5-8cc7cb32ea55}&action=embedview&AllowTyping=True&wdHideHeaders=True&wdInConfigurator=True&wdInConfigurator=True&ed1JS=false"></iframe>'.format(
                current_user.name, current_user.email, current_user.profile_pic
            )
        )
        """
    else:
        return render_template("login.html")


@app.route('/upload_images', methods=['POST'])
def upload_images():
    path = os.getcwd()
    global selected_project_name
    upload_folder_images = os.path.join(path, 'static', 'userdata', current_user.email, selected_project_name, 'images')
    print('upload dir: ' + upload_folder_images)
    app.config['UPLOAD_FOLDER'] = upload_folder_images
    if request.method == 'POST':
        images = request.files.getlist("images")
        print(str(request.files))
        print('Images: ' + str(images))
        print('Number of images for upload: ' + str(len(images)))
        for image in images:
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], image.filename))
        return redirect('/get_project_files?project=' + selected_project_name)

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    path = os.getcwd()
    global selected_project_name
    upload_folder_csv = os.path.join(path, 'static', 'userdata', current_user.email, selected_project_name, 'csv')
    print('upload dir: ' + upload_folder_csv)
    app.config['UPLOAD_FOLDER'] = upload_folder_csv
    if request.method == 'POST':
        csv = request.files.get("csv")
        print(str(request.files))
        print('csv: ' + str(csv))

        # delete existing csv in the folder
        for filename in os.listdir(upload_folder_csv):
            file_path = os.path.join(upload_folder_csv, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
              os.unlink(file_path)
             
        csv.save(os.path.join(app.config['UPLOAD_FOLDER'], csv.filename))

        # rename uploaded csv to mycsv.csv
        uploaded_file = os.path.join(upload_folder_csv, csv.filename)
        new_file = os.path.join(upload_folder_csv, "mycsv.csv")
        os.rename(uploaded_file, new_file)
        return redirect('/get_project_files?project=' + selected_project_name)

"""
@app.route("/upload_images")
def upload_images():
    if current_user.is_authenticated:
        # retrieve the user's images
        images_path = join(join('userdata', current_user.email), 'images')
        print('images_path: ' + images_path)
        onlyfiles = []
        if os.path.exists(images_path):
          onlyfiles = [f for f in listdir(images_path) if isfile(join(images_path, f))]

          images_with_csv_entries = onlyfiles
          print("images_with_csv_entries len: " + str(len(images_with_csv_entries)), file=sys.stderr)
          images_without_csv_entries = []

        return render_template("upload_images.html", name=current_user.name, email=current_user.email, profile_pic=current_user.profile_pic, images_with_csv_entries = images_with_csv_entries, images_without_csv_entries = images_without_csv_entries)
    else:
        return render_template("login.html")
"""


@app.route("/fill_excel")
def fill_excel():
    if current_user.is_authenticated:
        # retrieve the user's excel
        return render_template("fill_excel.html", name=current_user.name, email=current_user.email, profile_pic=current_user.profile_pic)
    else:
        return render_template("login.html")


@app.route("/login")
def login():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)


@app.route("/login/callback")
def callback():
    # Get authorization code Google sent back to you
    code = request.args.get("code")

    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    # Prepare and send request to get tokens! Yay tokens!
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    # Parse the tokens!
    client.parse_request_body_response(json.dumps(token_response.json()))

    # Now that we have tokens (yay) let's find and hit URL
    # from Google that gives you user's profile information,
    # including their Google Profile Image and Email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    # We want to make sure their email is verified.
    # The user authenticated with Google, authorized our
    # app, and now we've verified their email through Google!
    if userinfo_response.json().get("email_verified"):
        unique_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        picture = userinfo_response.json()["picture"]
        users_name = userinfo_response.json()["given_name"]
    else:
        return "User email not available or not verified by Google.", 400

    # Create a user in our db with the information provided
    # by Google
    user = User(
        id_=unique_id, name=users_name, email=users_email, profile_pic=picture
    )

    # Doesn't exist? Add to database
    if not User.get(unique_id):
        # create dir for the new user
        new_user_folder = os.path.join('.', 'static', 'userdata', user.email)
        print('creating new dir for user: ' + new_user_folder)
        if not os.path.exists(new_user_folder):
            os.makedirs(new_user_folder)

        User.create(unique_id, users_name, users_email, picture)

    # Begin user session by logging the user in
    login_user(user)

    # Send user back to homepage
    return redirect(url_for("index"))

# get projects using email
def get_projects():
    projects = []
    projects_path = os.path.join('.', 'static', 'userdata', current_user.email)
    print('projects_path: ' + str(projects_path))
    for name in os.listdir(projects_path):
        if os.path.isdir(os.path.join(projects_path, name)):
            projects.append(name)

    return projects

@app.route("/get_project_files")
def get_project_files():
    project_name = request.args.get('project')
    global selected_project_name
    selected_project_name = project_name
    print('project_name: ' + project_name)
    project_folder = os.path.join('.', 'static', 'userdata', current_user.email, project_name)
    images_path = join(project_folder, 'images')
    print('images_path: ' + images_path)
    onlyfiles = []
    if os.path.exists(images_path):
        onlyfiles = [f for f in listdir(images_path) if isfile(join(images_path, f))]
    global images_with_csv_entries
    images_with_csv_entries = onlyfiles
    print("images_with_csv_entries len: " + str(len(images_with_csv_entries)), file=sys.stderr)
    global images_without_csv_entries
    images_without_csv_entries = []
    global project_has_csv
    project_has_csv = False
    if os.path.exists(os.path.join(project_folder, 'csv', 'mycsv.csv')):
        project_has_csv = True
    return redirect('/') 

@app.route('/add_new_project', methods =["GET", "POST"])
def add_new_project():
  if request.method == "POST":
    new_project_folder_name = request.form.get("add_new_project")
    print('new_project_folder_name: ' + new_project_folder_name)
    new_project_folder = os.path.join('.', 'static', 'userdata', current_user.email, new_project_folder_name)
    if not os.path.exists(new_project_folder):
      os.makedirs(new_project_folder)
    new_project_images = os.path.join(new_project_folder, 'images')
    os.makedirs(new_project_images)
    new_project_csv = os.path.join(new_project_folder, 'csv')
    os.makedirs(new_project_csv)
    global selected_project_name
    selected_project_name = new_project_folder_name
    global project_has_csv
    project_has_csv = False
    return redirect('/')


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


def sync_images_csv():
    pass


if __name__ == "__main__":
    app.run(ssl_context="adhoc")
