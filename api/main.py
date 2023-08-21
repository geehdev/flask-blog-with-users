from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date 
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager,\
      login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("FLASK_SECRET_KEY")
app.jinja_env.globals['current_year'] = date.today().year

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("POSTGRES_URL_WITH_PSYCOPG2")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

Bootstrap(app)
ckeditor = CKEditor(app)
login_manager = LoginManager(app)
gravatar = Gravatar(app, default='retro', force_default=False, use_ssl=False, base_url=None)

@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(id = user_id).first()


##CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), nullable=False)
    password = db.Column(db.String(250), nullable=False)
    date_create = db.Column(db.DateTime(timezone=False), nullable=False)
    posts = db.relationship('BlogPost', backref='users', lazy=True)
    comments = db.relationship('Comment', backref='users', lazy=True)
    likes = db.relationship('Like', backref='users', lazy=True)

    def __repr__(self) -> str:
        return f"<User: {self.name}>"
    

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    custom_creation_data = db.Column(db.String(250), nullable=False)

    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    
    comments = db.relationship('Comment', backref='blog_posts', lazy=True)
    likes = db.relationship('Like', backref='blog_posts', lazy=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __repr__(self):
        return f"Post Title: {self.title} // author: {self.users.name}"


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    date_create = db.Column(db.DateTime(timezone=False), nullable=False)

    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __repr__(self):
        return f"Comment Author: {self.users.name}"


class Like(db.Model):
    __tablename__ = "likes"
    id = db.Column(db.Integer, primary_key=True)
    like = db.Column(db.Integer, nullable=False)
    date_create = db.Column(db.DateTime(timezone=False), nullable=False)

    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def has_liked_post(post_id):
        if current_user.is_authenticated and Like.query.filter_by(post_id=post_id, user_id=int(current_user.get_id())).count() > 0:
            return True
        else:
            return False

    def __repr__(self):
        return f"Like Author: {self.users.name}"


# CREATE ALL TABLES IN THE DATABASE
with app.app_context():
    db.create_all()  


def admin_only(func):
    @wraps(func)
    def inner_fuction(*args, **kwargs):
        if current_user.id != 1:
            return abort(code=403)
        
        return func(*args, **kwargs)

    return inner_fuction


@app.route('/')
def get_all_posts():
    all_posts = BlogPost.query.all()
    return render_template("index.html", posts=all_posts)


@app.route('/register', methods=['GET', 'POST'])
def register():
    register_form = RegisterForm()
    
    if register_form.validate_on_submit():
        hash_and_salted_password = generate_password_hash(register_form.password.data, method='pbkdf2', salt_length=8)
        
        if User.query.filter_by(email = register_form.email.data).first():
            flash(message="You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))
            
        new_user = User(
            name = register_form.name.data,
            email = register_form.email.data,
            password = hash_and_salted_password,
            date_create = date.today()
        )

        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)

        return redirect(url_for('get_all_posts'))
    
    return render_template("register.html", form=register_form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm()

    if login_form.validate_on_submit():
        user = User.query.filter_by(email = login_form.email.data).first()
        if user:
            if check_password_hash(pwhash=user.password, password=login_form.password.data):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else: 
                flash(message="Password incorrect, please try again.")
        else:
            flash(message="That email does not exist, please try again.")
        
        return redirect(url_for('login'))
            
    return render_template("login.html", form=login_form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    requested_post = BlogPost.query.filter_by(id = post_id).first()
    
    if requested_post == None:
        flash(message="Post not found!")
        return redirect(url_for('get_all_posts'))

    comment_form = CommentForm()

    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash(message="you need to log in to comment!")
            return redirect(url_for('show_post', post_id=post_id))
    
        new_comment = Comment(
            text = comment_form.comment_text.data,
            date_create = date.today(),
            post_id = requested_post.id,
            user_id = int(current_user.get_id())
            )
        
        db.session.add(new_comment)
        db.session.commit()

        return redirect(url_for('show_post', post_id=post_id))
    return render_template("post.html", post=requested_post, form=comment_form, has_liked=Like.has_liked_post(post_id=post_id))


@app.route('/add_like/<int:post_id>')
def like(post_id):
    if current_user.is_authenticated:
        likes = Like.query.filter_by(post_id=post_id, user_id=int(current_user.get_id())).first()

        if likes:
            db.session.delete(likes)
            db.session.commit()
        else:
            add_like = Like(
                like = 1,
                user_id = current_user.get_id(),
                post_id = post_id,
                date_create = date.today()
                ) 
            db.session.add(add_like)
            db.session.commit()
    else:
        flash(message="you need to log in to like!")
    
    return redirect(url_for('show_post', post_id=post_id))


@app.route("/new-post", methods=['GET', 'POST'])
@login_required
def add_new_post():
    form = CreatePostForm()

    if form.validate_on_submit():
        new_post = BlogPost(
            title = form.title.data,
            subtitle = form.subtitle.data,
            body = form.body.data,
            img_url = form.img_url.data,
            user_id = int(current_user.get_id()),
            custom_creation_data = date.today().strftime("%B %d, %Y"),
        )

        db.session.add(new_post)
        db.session.commit()
        
        return redirect(url_for("get_all_posts"))
    
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = BlogPost.query.filter_by(id=post_id).first()

    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.users.name,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()

        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@login_required
def delete_post(post_id):
    post_to_delete = BlogPost.query.filter_by(id=post_id).first()

    db.session.delete(post_to_delete)
    db.session.commit()

    return redirect(url_for('get_all_posts'))


@app.route('/delete_comment/<int:comment_id>/<int:post_id>')
@login_required
def delete_comment(comment_id, post_id):
    current_comment = Comment.query.filter_by(id=comment_id).first()

    db.session.delete(current_comment)
    db.session.commit()

    return redirect(url_for('show_post', post_id=post_id))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=['GET', 'POST'])
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=True)
