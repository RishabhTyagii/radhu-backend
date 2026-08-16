from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from .models import UserProfile, PAGES_MAP
from .serializers import UserSerializer


@api_view(['GET'])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf_token_view(request):
    return Response({'ok': True})


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@csrf_exempt
def login_view(request):
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')

    if not username or not password:
        return Response({'error': 'Username and password required'}, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(request, username=username, password=password)
    if user is not None:
        django_login(request, user)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return Response({
            'ok': True,
            'user': UserSerializer(user).data,
        })
    else:
        return Response({'error': 'Invalid username or password'}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    django_logout(request)
    return Response({'ok': True})


@api_view(['GET'])
@permission_classes([AllowAny])
def me_view(request):
    if request.user.is_authenticated:
        return Response({
            'authenticated': True,
            'user': UserSerializer(request.user).data,
        })
    return Response({'authenticated': False})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pages_map_view(request):
    return Response(PAGES_MAP)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def user_list_create(request):
    if request.method == 'GET':
        users = User.objects.all().order_by('-is_superuser', 'username')
        return Response(UserSerializer(users, many=True).data)

    username = str(request.data.get('username', '')).strip()
    password = request.data.get('password', '')
    allowed_pages = request.data.get('allowed_pages', [])
    is_superuser = request.data.get('is_superuser', False)

    if not username or not password:
        return Response({'error': 'Username and password are required'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({'error': f'Username "{username}" already exists!'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, password=password)
    user.is_superuser = bool(is_superuser)
    user.is_staff = bool(is_superuser)
    user.save()

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.allowed_pages = allowed_pages
    profile.save()

    return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def user_detail(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    profile, _ = UserProfile.objects.get_or_create(user=user_obj)

    if request.method == 'GET':
        return Response(UserSerializer(user_obj).data)

    elif request.method == 'DELETE':
        if user_obj.is_superuser and User.objects.filter(is_superuser=True).count() <= 1:
            return Response({'error': 'At least one superuser account must remain.'}, status=status.HTTP_400_BAD_REQUEST)
        user_obj.delete()
        return Response({'ok': True})

    new_password = request.data.get('password')
    if new_password:
        user_obj.set_password(new_password)

    if 'is_superuser' in request.data:
        user_obj.is_superuser = bool(request.data['is_superuser'])
        user_obj.is_staff = bool(request.data['is_superuser'])

    user_obj.save()

    if 'allowed_pages' in request.data:
        profile.allowed_pages = request.data.get('allowed_pages', [])
        profile.save()

    return Response(UserSerializer(user_obj).data)
