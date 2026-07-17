from dataclasses import dataclass

from sqlalchemy import func

from app.models import Category, Product
from app.services.audit_service import changed_values, record_audit_event


class CategoryOperationError(ValueError):
    def __init__(self, message, code, status_code=422, field=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.field = field


@dataclass(frozen=True)
class CategoryInput:
    name: str


def category_audit_values(category, product_count=None):
    values = {
        'name': category.name,
        'company_id': category.company_id,
    }
    if product_count is not None:
        values['product_count'] = int(product_count or 0)
    return values


def create_category(db_session, company, user, category_input):
    validate_category_input(db_session, company.id, category_input)
    category = Category(
        name=category_input.name,
        company_id=company.id,
    )
    db_session.add(category)
    db_session.flush()

    record_audit_event(
        'category_created',
        'category',
        category.id,
        f'Categoria {category.name} cadastrada pelo aplicativo Windows.',
        new_values=category_audit_values(category, 0),
        company_id=company.id,
        user=user,
        db_session=db_session,
    )
    db_session.flush()
    return category


def update_category(db_session, company, user, category_id, category_input):
    query = db_session.query(Category).filter(
        Category.id == category_id,
        Category.company_id == company.id,
    )
    bind = db_session.get_bind()
    if bind is not None and bind.dialect.name.startswith('mysql'):
        query = query.with_for_update()
    category = query.first()
    if category is None:
        raise CategoryOperationError(
            'Categoria não encontrada nesta adega.',
            'category_not_found',
            404,
        )

    validate_category_input(
        db_session,
        company.id,
        category_input,
        category_id=category.id,
    )
    old_values = category_audit_values(category)
    category.name = category_input.name
    db_session.flush()

    new_values = category_audit_values(category)
    old_diff, new_diff = changed_values(old_values, new_values)
    if old_diff or new_diff:
        record_audit_event(
            'category_updated',
            'category',
            category.id,
            f'Categoria {category.name} atualizada pelo aplicativo Windows.',
            old_values=old_diff,
            new_values=new_diff,
            company_id=company.id,
            user=user,
            db_session=db_session,
        )
    db_session.flush()
    return category


def delete_category(db_session, company, user, category_id):
    query = db_session.query(Category).filter(
        Category.id == category_id,
        Category.company_id == company.id,
    )
    bind = db_session.get_bind()
    if bind is not None and bind.dialect.name.startswith('mysql'):
        query = query.with_for_update()
    category = query.first()
    if category is None:
        raise CategoryOperationError(
            'Categoria não encontrada nesta adega.',
            'category_not_found',
            404,
        )

    product_count = db_session.query(Product.id).filter(
        Product.category_id == category.id,
        Product.company_id == company.id,
    ).count()
    if product_count:
        raise CategoryOperationError(
            'Não é possível excluir uma categoria com produtos vinculados.',
            'category_has_products',
            409,
        )

    audit_values = category_audit_values(category, product_count)
    category_id = category.id
    category_name = category.name
    db_session.delete(category)
    db_session.flush()

    record_audit_event(
        'category_deleted',
        'category',
        category_id,
        f'Categoria {category_name} excluída pelo aplicativo Windows.',
        old_values=audit_values,
        company_id=company.id,
        user=user,
        db_session=db_session,
    )
    db_session.flush()
    return category_id


def category_product_count(db_session, company_id, category_id):
    return db_session.query(Product.id).filter(
        Product.category_id == category_id,
        Product.company_id == company_id,
    ).count()


def validate_category_input(db_session, company_id, category_input, category_id=None):
    if not category_input.name:
        raise CategoryOperationError(
            'Informe o nome da categoria.',
            'category_name_required',
            422,
            'name',
        )

    duplicate_query = db_session.query(Category.id).filter(
        Category.company_id == company_id,
        func.lower(Category.name) == category_input.name.casefold(),
    )
    if category_id is not None:
        duplicate_query = duplicate_query.filter(Category.id != category_id)
    if duplicate_query.first() is not None:
        raise CategoryOperationError(
            'Já existe uma categoria com este nome nesta adega.',
            'category_already_exists',
            409,
            'name',
        )
