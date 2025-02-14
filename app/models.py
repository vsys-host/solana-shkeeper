from .db_import import db


class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    value = db.Column(db.String(250))    
    __table_args__ = (db.UniqueConstraint('id'), )


class Accounts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(70))
    crypto = db.Column(db.String(20))
    amount = db.Column(db.Numeric(precision=52, scale=26), default=0) 
    last_update = db.Column(db.DateTime, default=db.func.current_timestamp(),
                                        onupdate=db.func.current_timestamp()) 
    status = db.Column(db.String(10))
    type = db.Column(db.String(30))
    __table_args__ = (db.UniqueConstraint('id'), )


class Wallets(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pub_address = db.Column(db.String(70))
    priv_key = db.Column(db.String(1000))
    create_time = db.Column(db.DateTime, default=db.func.current_timestamp(),
                                        onupdate=db.func.current_timestamp())
    status = db.Column(db.String(10))
    type = db.Column(db.String(30))
    __table_args__ = (db.UniqueConstraint('id'), )