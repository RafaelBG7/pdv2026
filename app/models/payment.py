from app.extensions import db


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'))
    method = db.Column(db.String(50), default='money')
    amount = db.Column(db.Float, default=0.0)
    sale = db.relationship('Sale', back_populates='payments')
