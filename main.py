from flask import Flask, render_template, url_for, redirect, flash
from flask_bootstrap import Bootstrap5
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String
from werkzeug.security import generate_password_hash, check_password_hash
import os

from forms import RegisterForm, LoginForm

app = Flask(__name__)
app.config['SECRET_KEY'] = "8BYkEfBA6O6donzWlSihBXox7C0sKR6b"
Bootstrap5(app)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


# CREATE DATABASE
class Base(DeclarativeBase):
    pass


app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DB_URL', 'sqlite:///items.db')
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# Create a Item table for all available items
class Item(db.Model):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(250), nullable=False)
    price: Mapped[str] = mapped_column(Integer, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=True)
    users = relationship("Link", backref="items.id")


# Create a User table for all your registered users
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    items = relationship("Link", backref="users.id")


# Create a table that links items to users, when put inside the shopping cart
class Link(db.Model):
    __tablename__ = "link"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    item_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("items.id"))
    amount: Mapped[int] = mapped_column(Integer, nullable=False)


with app.app_context():
    db.create_all()


@app.route("/")
def home():
    result = db.session.execute(db.select(Item))
    items = result.scalars().all()
    return render_template("index.html", all_items=items, current_user=current_user)


# Register new users into the User database
@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():

        # Check if user email is already present in the database.
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result.scalar()
        if user:
            # User already exists
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))

        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=form.email.data,
            name=form.name.data,
            password=hash_and_salted_password,
        )
        db.session.add(new_user)
        db.session.commit()
        # This line will authenticate the user with Flask-Login
        login_user(new_user)
        return redirect(url_for("home"))
    return render_template("register.html", form=form, current_user=current_user)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        password = form.password.data
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        # Note, email in db is unique so will only have one result.
        user = result.scalar()
        # Email doesn't exist
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        # Password incorrect
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('home'))

    return render_template("login.html", form=form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


# Add a Item to the cart
@app.route("/add/<int:item_id>")
def add_to_cart(item_id):
    # Only allow logged-in users to add items to their cart
    if not current_user.is_authenticated:
        flash("You need to login or register to select items.")
        return redirect(url_for("login"))

    # check if item is already linked to user
    result = db.session.execute(db.select(Link).where(Link.user_id == current_user.id).where(Link.item_id == item_id))
    existing_link = result.scalar()
    if existing_link:
        existing_link.amount += 1
        db.session.commit()
    else:
        new_link = Link(
            item_id=item_id,
            user_id=current_user.id,
            amount=1
        )
        db.session.add(new_link)
        db.session.commit()
    return redirect(url_for('home'))


# Show Items in Users cart
@app.route("/cart")
def show_cart():
    result = db.session.execute(db.select(Link).where(Link.user_id == current_user.id))
    user_links = result.scalars().all()
    sum = 0
    items = []
    for link in user_links:
        result = db.session.execute(db.select(Item).where(Item.id == link.item_id))
        cart_item = result.scalar()
        items.append(cart_item)
        sum += link.amount * cart_item.price
    return render_template("cart.html", cart_items=items, sum=sum, current_user=current_user, links=user_links, zip=zip, format=format)

@app.route("/increase/<int:link_id>")
def increase_amount(link_id):
    # Only allow logged-in users to add items to their cart
    if not current_user.is_authenticated:
        flash("You need to login or register to select items.")
        return redirect(url_for("login"))

    link = db.get_or_404(Link, link_id)
    link.amount += 1
    db.session.commit()
    return redirect(url_for("show_cart"))


@app.route("/decrease/<int:link_id>")
def decrease_amount(link_id):
    # Only allow logged-in users to add items to their cart
    if not current_user.is_authenticated:
        flash("You need to login or register to select items.")
        return redirect(url_for("login"))

    link = db.get_or_404(Link, link_id)
    if link.amount == 1:
        db.session.delete(link)
        db.session.commit()
    else:
        link.amount -= 1
        db.session.commit()
    return redirect(url_for("show_cart"))


if __name__ == '__main__':
    app.run(debug=True)