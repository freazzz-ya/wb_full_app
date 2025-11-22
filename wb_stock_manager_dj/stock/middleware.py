import logging
from django.shortcuts import render

logger = logging.getLogger(__name__)

class ErrorHandlerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        logger.error(f"Exception occurred: {str(exception)}", exc_info=True)
        return None