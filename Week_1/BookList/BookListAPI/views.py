from django.shortcuts import render

# Create your views here.
from django.db import IntegrityError
from django.http import JsonResponse
from .models import Book
from django.views.decorators.csrf import csrf_exempt
from django.forms.models import model_to_dict



@csrf_exempt
def books(request):
    if request.method == "GET":
        called_books = Book.objects.all().values()
        print(called_books)

        return JsonResponse({
            "books": list(called_books)
        })
    elif request == "POST":
        title = request.POST.get("title")
        author = request.POST.get("author")
        price = request.POST.get("price")


        try:
            book = Book(title, author, price)
            book.save()
        except IntegrityError:
            return JsonResponse(
                {
                    "error": "true",
                    "message": "required field missing"
                },
                status=400
            )

        return JsonResponse(
            model_to_dict(book),
            status=201
        )
