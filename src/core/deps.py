# from fastapi import Depends, HTTPException, status
# from fastapi.security import OAuth2PasswordBearer
# from sqlalchemy.orm import Session

# from src.core.database import get_db
# from src.core.security import decode_token
# from src.models.user import User

# # Request Header se "Authorization: Bearer <token>" extract karne ke liye
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# def get_current_user(
#     token: str = Depends(oauth2_scheme),
#     db: Session = Depends(get_db)
# ) -> User:
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )

#     # 1. Token decode karein
#     payload = decode_token(token)
#     if not payload:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid or expired token"
#         )

#     # 2. Check token type (Access token hi hona chahiye, Refresh token nahi)
#     if payload.get("type") != "access":
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid token type"
#         )

#     user_id: str = payload.get("sub")
#     if user_id is None:
#         raise credentials_exception

#     # 3. Database se active user fetch karein
#     user = db.query(User).filter(User.id == int(user_id)).first()
#     if user is None:
#         raise credentials_exception

#     if not user.is_active:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Inactive user account"
#         )

#     return user