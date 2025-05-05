from flask import Blueprint

conversation_bp = Blueprint('conversation_bp', __name__)

from .routes import *
