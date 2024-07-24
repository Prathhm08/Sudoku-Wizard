from flask import Flask, request, redirect, url_for, render_template, flash, send_file
from werkzeug.utils import secure_filename
import datetime
import firebase_admin
from firebase_admin import credentials, storage
from sudoku_solver import solve_sudoku_image
from io import BytesIO
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_secret_key")

# Firebase initialization
cred = credentials.Certificate(
    {
        "type": "service_account",
        "projectId": os.getenv("FIREBASE_PROJECT_ID"),
        "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
        "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    }
)

firebase_admin.initialize_app(
    cred, {"storageBucket": os.getenv("FIREBASE_BUCKET_NAME")}
)
bucket = storage.bucket()


def upload_image_to_firebase(image_bytes, filename, folder):
    blob = bucket.blob(f"{folder}/{filename}")
    blob.upload_from_string(image_bytes, content_type="image/jpeg")
    return blob.generate_signed_url(expiration=datetime.timedelta(hours=1))


def download_image_from_firebase(filename):
    blob = bucket.blob(f"uploaded_images/{filename}")
    return blob.download_as_bytes()


@app.route("/", methods=["GET", "POST"])
def upload_image():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file part")
            return redirect(request.url)
        file = request.files["file"]
        if file.filename == "":
            flash("No image selected for uploading")
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            blob = bucket.blob(f"uploaded_images/{filename}")
            blob.upload_from_file(file)
            image_bytes = download_image_from_firebase(filename)
            try:
                solved_image_bytes = solve_sudoku_image(image_bytes)
                if solved_image_bytes:
                    solved_filename = f"solved_{filename}"
                    solved_image_url = upload_image_to_firebase(
                        solved_image_bytes, solved_filename, "solved_images"
                    )
                    return render_template(
                        "index.html",
                        filename=filename,
                        solved_filename=solved_filename,
                        solved_image_url=solved_image_url,
                    )
                else:
                    flash(
                        "Could not solve Sudoku, please upload clear and valid image of sudoku!"
                    )
                    return redirect(request.url)
            except Exception as e:
                flash(
                    f"Error solving Sudoku: Please upload clear and valid image of sudoku!"
                )
                return redirect(request.url)
        else:
            flash("Allowed image types are - png, jpg, jpeg, gif")
            return redirect(request.url)
    return render_template("index.html")


@app.route("/display/<filename>")
def display_image(filename):
    try:
        blob = bucket.blob(f"solved_images/{filename}")
        if blob.exists():
            image_bytes = blob.download_as_bytes()
        else:
            blob = bucket.blob(f"uploaded_images/{filename}")
            if blob.exists():
                image_bytes = blob.download_as_bytes()
            else:
                return "Image not found", 404

        return send_file(BytesIO(image_bytes), mimetype="image/jpeg")
    except Exception as e:
        print(f"Error: {e}")
        return "Image not found", 404


@app.route("/clear_uploads", methods=["POST"])
def clear_uploads():
    try:
        uploaded_blobs = bucket.list_blobs(prefix="uploaded_images/")
        for blob in uploaded_blobs:
            blob.delete()
        solved_blobs = bucket.list_blobs(prefix="solved_images/")
        for blob in solved_blobs:
            blob.delete()
    except Exception as e:
        flash(f"Error clearing uploads: {e}")
    return redirect(url_for("upload_image"))


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {
        "jpg",
        "jpeg",
        "png",
    }


if __name__ == "__main__":
    app.run(debug=True)
