from flask import Blueprint

from app.version import __version__
from toolset import ApiResponse


api = Blueprint('main', __name__)


@api.route('/info', methods=['GET'])
def info():
    return ApiResponse({
        'version': __version__
    })
