from sqlalchemy import create_engine, Column, Integer, String, ForeignKey,UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Create the database engine
engine = create_engine('sqlite:///medicine.db')
Base = declarative_base(bind=engine)
Session = sessionmaker(bind=engine)
session = Session()

# Define the User model
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, unique=True, nullable=False)
    
    medicine_intervals = relationship('MedicineInterval', back_populates='user', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<User(chat_id={self.chat_id})>"

# Define the MedicineInterval model
class MedicineInterval(Base):
    __tablename__ = 'medicine_intervals'
    
    id = Column(Integer, primary_key=True)
    interval = Column(String, nullable=False)
    hour = Column(String, nullable=False)
    medicine_name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'))
    next_run = Column(Integer, nullable=False)

    
    user = relationship('User', back_populates='medicine_intervals')
    __table_args__ = (
        UniqueConstraint('medicine_name', 'hour', 'interval'),
    )
    def __repr__(self):
        return f"<MedicineInterval(interval={self.interval}, user_id={self.user_id})>"

# Create the database tables (if they don't exist)
Base.metadata.create_all()

Session = sessionmaker(bind=engine)
session = Session()

# To mock some dummy data
# medicine_interval = MedicineInterval(
#         medicine_name='xanax',
#         user_id=1,
#         hour='12:00',
#         interval=2,
#         next_run=1685197633)

# medicine_interval = session.query(MedicineInterval).get(4)
# session.delete(medicine_interval)
# session.commit()
# session.add(medicine_interval)
