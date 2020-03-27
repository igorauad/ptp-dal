from flask_sqlalchemy import SQLAlchemy
import logging

logger = logging.getLogger(__name__)
db     = SQLAlchemy()

class Dataset(db.Model):
    __tablename__ = 'datasets'

    id                 = db.Column(db.Integer, primary_key=True)
    name               = db.Column(db.String(120), unique=True, nullable=False)
    oscillator         = db.Column(db.String(20), nullable=False)
    sync_period        = db.Column(db.Float, nullable=False)
    hops_rru1          = db.Column(db.Integer)
    hops_rru2          = db.Column(db.Integer)
    n_rru_ptp          = db.Column(db.Integer)
    delay_cal          = db.Column(db.Boolean)
    delay_cal_duration = db.Column(db.Integer)
    pipeline_bbu       = db.Column(db.Integer)
    pipeline_rru       = db.Column(db.Integer)
    start_time         = db.Column(db.DateTime)
    fh_traffic         = db.Column(db.Boolean, nullable=False)
    fh_type            = db.Column(db.String(20))
    fh_fs              = db.Column(db.Float)
    fh_iq_size_dl      = db.Column(db.Integer)
    fh_iq_size_ul      = db.Column(db.Integer)
    fh_bitrate_dl      = db.Column(db.Float)
    fh_bitrate_ul      = db.Column(db.Float)
    fh_n_spf_dl        = db.Column(db.Integer)
    fh_n_spf_ul        = db.Column(db.Integer)
    fh_n_rru_ul        = db.Column(db.Integer)
    fh_n_rru_dl        = db.Column(db.Integer)

    def __repr__(self):
        return f"Dataset {self.name}"

    def save(self):
        """Save model on the database"""

        try:
            db.session.add(self)
            db.session.commit()
            logger.info(f"Saved {self} on database")
        except:
            logger.warning(f"Unable to save {self} on database")

    def delete(self):
        """Delete model from the database"""

        db.session.delete(self)
        db.session.commit()

    @classmethod
    def drop_all(cls):
        try:
            db.drop_all()
            logger.info("Dropped all database tables")
        except:
            logger.warning("Unable to drop database tables")

    @classmethod
    def create_all(cls):
        try:
            db.create_all()
            logger.info("Created all database tables")
        except:
            logger.warning("Unable to create database tables")

    @classmethod
    def search(cls, parameters):
        """Apply a query on the database based on the passed parameters

        Args:
            parameters: Dictionary with all the possible parameters

        """
        filtered_par = {k: v for k, v in parameters.items() if v is not None}
        return cls.query.filter_by(**filtered_par).all()


