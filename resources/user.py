import os
import requests
# import redis
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from passlib.hash import pbkdf2_sha256
from flask_jwt_extended import create_access_token, get_jwt, jwt_required, create_refresh_token, get_jwt_identity
#     
#     get_jwt,
# )
# from rq import Queue
from sqlalchemy import or_

from db import db
from blocklist import BLOCKLIST
from models import UserModel
from schemas import UserSchema, UserRegisterSchema
# from tasks import send_user_registration_email


blp = Blueprint("Users", "users", description="Operations on users")

def send_simple_message(to, subject, body):
    domain = os.getenv("MAILGUN_DOMAIN")
    return requests.post(
  		f"https://api.mailgun.net/v3/{domain}/messages",
  		auth=("api", os.getenv("MAILGUN_API_KEY")),
  		data={"from": f"Christian Ibeto <mailgun@{domain}>",
			"to": [to],
  			"subject": subject,
  			"text": body})

@blp.route("/register")
class UserRegister(MethodView):
    @blp.arguments(UserRegisterSchema)
    def post(self, user_data):
        if UserModel.query.filter(
            or_(
            UserModel.username == user_data["username"],
            UserModel.email == user_data["email"]
            )
        ).first():
            abort(409, message="A user with that username or email already exists.")

        user = UserModel(
            username=user_data["username"],
            email=user_data["email"],
            password=pbkdf2_sha256.hash(user_data["password"])
        )
        db.session.add(user)
        db.session.commit()
        send_simple_message(
            to=user.email,
            subject="Successfully Signed Up",
            body=f"Hi {user.username}! You have signed up for the STORES REST APIs"
        )

        return {"message": "User created successfully."}, 201


# connection = redis.from_url(
#     os.getenv("REDIS_URL")
# )  # Get this from Render.com or run in Docker
# queue = Queue("emails", connection=connection)


@blp.route("/login")
class UserLogin(MethodView):
    @blp.arguments(UserSchema)
    def post(self, user_data):
        user = UserModel.query.filter(
            UserModel.username == user_data["username"]
        ).first()

        if user and pbkdf2_sha256.verify(user_data["password"], user.password):
            access_token = create_access_token(identity=str(user.id), fresh=True)
            refresh_token = create_refresh_token(identity=str(user.id))
            return {"access_token": access_token, "refresh_token": refresh_token}

        abort(401, message="Invalid credentials.")


@blp.route("/refresh")
class TokenRefresh(MethodView):
    @jwt_required(refresh=True)
    def post(self):
        current_user = get_jwt_identity()
        new_token = create_access_token(identity=current_user, fresh=False)
        return {"access_token": new_token}


@blp.route("/logout")
class UserLogout(MethodView):
    @jwt_required()
    def post(self):
        jti = get_jwt()["jti"]
        BLOCKLIST.add(jti)
        return {"message": "Successfully logged out."}


@blp.route("/user/<int:user_id>")
class User(MethodView):
    @blp.response(200, UserSchema)
    def get(self, user_id):
        user = UserModel.query.get_or_404(user_id)
        return user

    def delete(self, user_id):
        user = UserModel.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        return {"message": "User deleted."}, 200
