from rosman_extensions import db


class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    created_at = db.Column(db.Text, nullable=False, server_default=db.text("CURRENT_TIMESTAMP"))

    users = db.relationship("User", back_populates="organization")
    staff_members = db.relationship("Staff", back_populates="organization")
    shift_templates = db.relationship("ShiftTemplate", back_populates="organization")
    roster_assignments = db.relationship("RosterAssignment", back_populates="organization")
    staff_availability_entries = db.relationship("StaffAvailability", back_populates="organization")
    staff_shift_preferences = db.relationship("StaffShiftPreference", back_populates="organization")


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.Text, nullable=False, unique=True)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(db.Text, nullable=False, server_default=db.text("'owner'"))
    org_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = db.Column(db.Text, nullable=False, server_default=db.text("CURRENT_TIMESTAMP"))

    organization = db.relationship("Organization", back_populates="users")


class Staff(db.Model):
    __tablename__ = "staff"

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.Text, nullable=False)
    role = db.Column(db.Text, nullable=False)
    email = db.Column(db.Text)
    active = db.Column(db.Integer, nullable=False, server_default=db.text("1"))
    created_at = db.Column(db.Text, nullable=False, server_default=db.text("CURRENT_TIMESTAMP"))

    roster_assignments = db.relationship(
        "RosterAssignment",
        back_populates="staff",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    availability_entries = db.relationship(
        "StaffAvailability",
        back_populates="staff",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    shift_preferences = db.relationship(
        "StaffShiftPreference",
        back_populates="staff",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    organization = db.relationship("Organization", back_populates="staff_members")


class ShiftTemplate(db.Model):
    __tablename__ = "shift_templates"
    __table_args__ = (db.UniqueConstraint("org_id", "name", name="uq_shift_templates_org_name"),)

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.Text, nullable=False)
    start_time = db.Column(db.Text, nullable=False)
    end_time = db.Column(db.Text, nullable=False)
    required_staff = db.Column(db.Integer, nullable=False, server_default=db.text("1"))

    roster_assignments = db.relationship(
        "RosterAssignment",
        back_populates="shift_template",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    staff_preferences = db.relationship(
        "StaffShiftPreference",
        back_populates="shift_template",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    organization = db.relationship("Organization", back_populates="shift_templates")


class RosterAssignment(db.Model):
    __tablename__ = "roster_assignments"
    __table_args__ = (
        db.UniqueConstraint("org_id", "roster_date", "staff_id", "shift_id", name="uq_roster_org_date_staff_shift"),
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    roster_date = db.Column(db.Text, nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    shift_id = db.Column(
        db.Integer,
        db.ForeignKey("shift_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    notes = db.Column(db.Text)

    staff = db.relationship("Staff", back_populates="roster_assignments")
    shift_template = db.relationship("ShiftTemplate", back_populates="roster_assignments")
    organization = db.relationship("Organization", back_populates="roster_assignments")


class StaffAvailability(db.Model):
    __tablename__ = "staff_availability"

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    start_date = db.Column(db.Text, nullable=False)
    end_date = db.Column(db.Text, nullable=False)
    status = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text)

    staff = db.relationship("Staff", back_populates="availability_entries")
    organization = db.relationship("Organization", back_populates="staff_availability_entries")


class StaffShiftPreference(db.Model):
    __tablename__ = "staff_shift_preferences"

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    shift_id = db.Column(
        db.Integer,
        db.ForeignKey("shift_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    start_date = db.Column(db.Text, nullable=False)
    end_date = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text)

    staff = db.relationship("Staff", back_populates="shift_preferences")
    shift_template = db.relationship("ShiftTemplate", back_populates="staff_preferences")
    organization = db.relationship("Organization", back_populates="staff_shift_preferences")
