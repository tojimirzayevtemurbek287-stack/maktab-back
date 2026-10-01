"""Kirish va ro'yxatdan o'tish: o'quvchi ham, o'qituvchi ham o'zi ro'yxatdan o'tadi."""
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.validators import UnicodeUsernameValidator
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SchoolClass, User
from .views import AuthThrottle, auth_response


class SignUpSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=["student", "teacher"], default="student")
    school_class = serializers.PrimaryKeyRelatedField(
        queryset=SchoolClass.objects.all(), required=False, allow_null=True
    )
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)

    class Meta:
        model = User
        fields = ["username", "password", "first_name", "last_name", "role", "school_class"]
        extra_kwargs = {"username": {"validators": [UnicodeUsernameValidator()]}}

    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Bu login band. Boshqa login tanlang.")
        return value

    def validate(self, attrs):
        if attrs["role"] == "student" and not attrs.get("school_class"):
            raise serializers.ValidationError({"school_class": "Sinfingizni tanlang."})
        if attrs["role"] == "teacher":
            attrs["school_class"] = None
        password_validation.validate_password(
            attrs["password"], User(username=attrs.get("username", ""))
        )
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.is_approved = user.role != "teacher"  # o'qituvchini administrator tasdiqlaydi
        user.set_password(password)
        user.save()
        return user


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        user = authenticate(
            username=(request.data.get("username") or "").strip(),
            password=request.data.get("password") or "",
        )
        if not user:
            return Response(
                {"detail": "Login yoki parol noto'g'ri."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.is_approved:
            return Response(
                {"detail": "Akkauntingiz hali administrator tomonidan tasdiqlanmagan. Tasdiqlangach kira olasiz."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(auth_response(user))


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = SignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        if not user.is_approved:
            return Response(
                {
                    "pending": True,
                    "detail": "Arizangiz qabul qilindi. Administrator tasdiqlagach, login va parolingiz bilan kira olasiz.",
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(auth_response(user), status=status.HTTP_201_CREATED)
