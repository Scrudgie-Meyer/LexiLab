"""
lexilab — /datasets routes
CRUD for user datasets.
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from db.database import get_db
from db.models import Dataset, User
from api.schemas import DatasetCreate, DatasetOut, DatasetListOut

router = APIRouter(prefix="/datasets", tags=["datasets"])


# ── get or create anonymous user by session_id ──
async def get_or_create_user(session_id: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.session_id == session_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(session_id=session_id)
        db.add(user)
        await db.flush()
    return user


# ─────────────────────────────────────────────
# LIST public datasets
# GET /datasets
# ─────────────────────────────────────────────
@router.get("/", response_model=DatasetListOut)
async def list_datasets(
    lang: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    sort: str = "newest",
    db: AsyncSession = Depends(get_db),
):
    query = select(Dataset).where(Dataset.is_public == True)
    if lang:
        query = query.where(Dataset.lang == lang)

    total_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_q)).scalar()

    if sort == "oldest":
        query = query.order_by(Dataset.created_at.asc())
    elif sort == "lang":
        query = query.order_by(Dataset.lang, Dataset.created_at.desc())
    else:  # newest
        query = query.order_by(Dataset.created_at.desc())

    query  = query.offset(skip).limit(limit)
    result = await db.execute(query)
    items  = result.scalars().all()

    return DatasetListOut(total=total, items=items)


# ─────────────────────────────────────────────
# GET one dataset
# GET /datasets/{id}
# ─────────────────────────────────────────────
@router.get("/{dataset_id}", response_model=DatasetOut)
async def get_dataset(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


# ─────────────────────────────────────────────
# CREATE dataset (raw upload — no analysis yet)
# POST /datasets
# ─────────────────────────────────────────────
@router.post("/", response_model=DatasetOut, status_code=201)
async def create_dataset(
    payload: DatasetCreate,
    x_session_id: str = Header(..., alias="X-Session-Id"),
    db: AsyncSession = Depends(get_db),
):
    user = await get_or_create_user(x_session_id, db)

    dataset = Dataset(
        user_id   = user.id,
        name      = payload.name,
        raw_text  = payload.text,
        is_public = payload.is_public,
    )
    db.add(dataset)
    await db.flush()
    await db.refresh(dataset)
    return dataset


# ─────────────────────────────────────────────
# DELETE dataset
# DELETE /datasets/{id}
# ─────────────────────────────────────────────
@router.delete("/{dataset_id}", status_code=204)
async def delete_dataset(
    dataset_id: int,
    x_session_id: str = Header(..., alias="X-Session-Id"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Dataset)
        .join(User)
        .where(Dataset.id == dataset_id)
        .where(User.session_id == x_session_id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found or not yours")
    await db.delete(dataset)