import requests
import random
import string
import time
from json import JSONEncoder
from datetime import datetime
from django.conf import settings
from django.core import serializers
from django.shortcuts import render , get_object_or_404
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password , check_password
from .models import User, Token, Expense, Income, Passwordresetcodes, News
from postmark import PMMail
from django.db.models import Sum, Count
from django.views.decorators.http import require_POST
from .utils import grecaptcha_verify, RateLimited

# Create your views here.

random_str = lambda N: ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(N))



@csrf_exempt
def news(request):
    news = News.objects.all().order_by('-date')[:11]
    news_serialized = serializers.serialize("json", news)
    return JsonResponse(news_serialized, encoder=JSONEncoder, safe=False)

@csrf_exempt
@require_POST
def login(request):
    if request.POST.__contains__('username') and request.POST.__contains__('password'):
        username = request.POST['username']    
        password = request.POST['password']
        this_user = get_object_or_404(User, username = username)
        if (check_password(password, this_user.password)):
            this_token = get_object_or_404(Token, user = this_user)
            token = this_token.token 
            context = {}
            context['result'] = 'ok'
            context['token'] = token
            return JsonResponse(context, encoder=JSONEncoder)
        
        else:
            context = {}
            context['result'] = 'error'
            return JsonResponse(context, encoder=JSONEncoder)    
        
def register(request):
    if request.POST.__contains__('requestcode'): #form is filled. if not spam, generate code and save in db, wait for email confirmation, return message
        # is this spam? check reCaptcha
        # if not grecaptcha_verify(request): # captcha was not correct
        #     context = {'message': 'کپچای گوگل درست وارد نشده بود. شاید ربات هستید؟ کد یا کلیک یا تشخیص عکس زیر فرم را درست پر کنید. ببخشید که فرم به شکل اولیه برنگشته!'} #TODO: forgot password
        #     return render(request, 'register.html', context)
        # if not grecaptcha_verify(request):  # captcha was not correct
        #     context = {
        #         'message': 'کپچای گوگل درست وارد نشده بود. شاید ربات هستید؟ کد یا کلیک یا تشخیص عکس زیر فرم را درست پر کنید. ببخشید که فرم به شکل اولیه برنگشته!'}  # TODO: forgot password
        #     return render(request, 'register.html', context)

        if User.objects.filter(email = request.POST['email']).exists(): # duplicate email
            context = {'message': 'متاسفانه این ایمیل قبلا استفاده شده است. در صورتی که این ایمیل شما است، از صفحه ورود گزینه فراموشی پسورد رو انتخاب کنین. ببخشید که فرم ذخیره نشده. درست می شه'} #TODO: forgot password
            #TODO: keep the form data
            return render(request, 'register.html', context)

        if not User.objects.filter(username = request.POST['username']).exists(): #if user does not exists
                code = random_str(28)
                now = datetime.now()
                email = request.POST['email']
                password = make_password(request.POST['password'])
                username = request.POST['username']
                temporarycode = Passwordresetcodes (email = email, time = now, code = code, username=username, password=password)
                temporarycode.save()
                message = PMMail(api_key = settings.POSTMARK_API_TOKEN,
                                 subject = "فعال سازی اکانت بستون",
                                 sender = "njesntd@telegmail.com",
                                 to = email,
                                 text_body = "برای فعال سازی اکانت بستون خود روی لینک روبرو کلیک کنید: {}?email={}&code={}".format(request.build_absolute_uri('/accounts/register/'), email, code),
                                 tag = "Account Request")
                message.send()
                context = {'message': 'ایمیلی حاوی لینک فعال سازی اکانت به شما فرستاده شده، لطفا پس از چک کردن ایمیل، روی لینک کلیک کنید.'}
                return render(request, 'index.html', context)
        else:
            context = {'message': 'متاسفانه این نام کاربری قبلا استفاده شده است. از نام کاربری دیگری استفاده کنید. ببخشید که فرم ذخیره نشده. درست می شه'} #TODO: forgot password
            #TODO: keep the form data
            return render(request, 'register.html', context)
    elif request.GET.__contains__('code'): # user clicked on code
        email = request.GET['email']
        code = request.GET['code']
        if Passwordresetcodes.objects.filter(code=code).exists(): #if code is in temporary db, read the data and create the user
            new_temp_user = Passwordresetcodes.objects.get(code=code)
            newuser = User.objects.create(username=new_temp_user.username, password=new_temp_user.password, email=email)
            this_token = random_str(48)
            token = Token.objects.create(user=newuser, token=this_token)
            Passwordresetcodes.objects.filter(code=code).delete() #delete the temporary activation code from db
            context = {'message': 'اکانت شما ساخته شد. توکن شما {}'.format(this_token)}
            return render(request, 'index.html', context)
        else:
            context = {'message': 'این کد فعال سازی معتبر نیست. در صورت نیاز دوباره تلاش کنید'}
            return render(request, 'register.html', context)
    else:
        context = {'message': ''}
        return render(request, 'register.html', context)

@csrf_exempt
@require_POST
def whoami(request):
        this_token = request.POST['token']  # TODO: Check if there is no `token`- done-please Check it
        # Check if there is a user with this token; will retun 404 instead.
        this_user = get_object_or_404(User, token__token=this_token)

        return JsonResponse({
            'user': this_user.username,
        }, encoder=JSONEncoder)

@csrf_exempt
@require_POST
def query_expenses(request):
    this_token = request.POST['token']
    num = request.POST.get('num', 10)
    this_user = get_object_or_404(User, token__token = this_token)
    expenses = Income.objects.filter(user = this_user).order_by('-date')[:num]
    expenses_serialized = serializers.serialize("json", expenses)
    return JsonResponse(expenses_serialized, encoder=JSONEncoder, safe=False)

@csrf_exempt
@require_POST
def query_incomes(request):
    this_token = request.POST['token']
    num = request.POST.get('num', 10)
    this_user = get_object_or_404(User, token__token = this_token)
    incomes = Income.objects.filter(user = this_user).order_by('-date')[:num]
    incomes_serialized = serializers.serialize("json", incomes)
    return JsonResponse(incomes_serialized, encoder=JSONEncoder, safe=False)

@csrf_exempt
@require_POST
def generalstat(request):
    this_token = request.POST['token']
    this_user = get_object_or_404(User, token__token = this_token)
    income = Income.objects.filter(user = this_user).aggregate(Count('amount'), Sum('amount'))
    expense = Expense.objects.filter(user = this_user).aggregate(Count('amount'), Sum('amount'))
    context = {}
    context['expense'] = expense
    context['income'] = income
    return JsonResponse(context, encoder=JSONEncoder)


def index(request):
    context = {}
    return render(request, 'index.html', context)


@csrf_exempt
@require_POST
def submit_income(request):
    this_token = request.POST['token']
    this_user = get_object_or_404(User, token__token = this_token)
    if 'date' not in request.POST:
        date = datetime.now()
    else:
        date = request.POST['date']
    Income.objects.create(user = this_user, amount=request.POST['amount'],
                          text = request.POST['text'], date=date)
    
    return JsonResponse({
        'status': 'ok'
    }, encoder=JSONEncoder)

@csrf_exempt
@require_POST
def submit_expense(request):
    this_token = request.POST['token']
    this_user = get_object_or_404(User, token__token = this_token)
    if 'date' not in request.POST:
        date = datetime.now()
    else:
        date = request.POST['date']
    Expense.objects.create(user = this_user, amount=request.POST['amount'],
                           text = request.POST['text'], date=date)
    
    return JsonResponse({
        'status': 'ok'
    }, encoder=JSONEncoder)