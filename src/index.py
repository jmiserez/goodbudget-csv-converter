from __future__ import print_function # In python 2.7
import os, csv, io, sys, copy
from flask import Flask, request, redirect, url_for, flash, render_template, Response, stream_with_context
from werkzeug import secure_filename
from werkzeug.wsgi import LimitedStream
from Tix import ROW

ALLOWED_EXTENSIONS = set(['csv', 'CSV','txt','TXT'])

app = Flask(__name__)
MAX_FILE_SIZE = (4 * 1024 * 1024)
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE #will raise RequestEntityTooLarge

@app.errorhandler(Exception)
def all_exception_handler(error):
    return render_template('index.html', messages=["Unhandled error (500 internal server error): " + str(error),])

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

def index_render_with_messages(messages):
    return render_template('index.html', messages=messages)

@app.route("/", methods=['GET', 'POST'])
def index():
    messages = [] # don't want to use flash()
    if request.method == 'POST':
        cl = request.content_length
        if cl is not None and cl > MAX_FILE_SIZE:
            messages.append('Error: File is too large. Select a file smaller than 4MB. Write me an email if you need to process a larger file.')
            return index_render_with_messages(messages)
        # based on: http://flask.pocoo.org/docs/0.11/patterns/fileuploads/
        # check if the post request has the file part
        if 'file' not in request.files:
            messages.append('Error: No file selected for upload! Select a file before pressing "Convert".')
            return index_render_with_messages(messages)
        uploaded_file = request.files['file']
        # if user does not select file, browser also
        # submit a empty part without filename
        if uploaded_file.filename == '':
            messages.append('Error: No file selected for upload! Select a file before pressing "Convert".')
            return index_render_with_messages(messages)
        if uploaded_file and not allowed_file(uploaded_file.filename):
            messages.append('Error: File name does not end with .csv or .txt!  Select a .csv/.txt file before pressing "Convert".')
            return index_render_with_messages(messages)
        lines = uploaded_file.readlines()
        return stream_data(lines)
        
    return index_render_with_messages(messages)

def stream_data(lines):
    def generate(lines):
        DETAILS = 'Details'
        ENVELOPE = 'Envelope'
        AMOUNT = 'Amount'
        output = io.BytesIO()
        reader = csv.DictReader(f=lines)
        writer = csv.DictWriter(f=output, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            assert DETAILS in row
            assert ENVELOPE in row
            assert AMOUNT in row
            details = row.get(DETAILS)
            envelope = row.get(ENVELOPE)
            amount = row.get(AMOUNT)
            if len(details) > 0:
                # details not empty
                splits = details.split('||')
                assert len(splits) > 0
                for transaction_str in splits:
                    # envelope|amount, or in the case of income: "[Unallocated]|amount
                    # - note that although the Unallocated envelope cannot be accurately tracked (as fills always have amount 0 in the csv), 
                    #   adding this will enable tracking/verifying of at least the overall amount over all envelopes.
                    transaction_pair = transaction_str.split('|')
                    assert len(transaction_pair) == 2
                    new_envelope = transaction_pair[0]
                    new_amount = transaction_pair[1]
                    new_row = copy.deepcopy(row)
                    new_row[ENVELOPE] = new_envelope
                    new_row[AMOUNT] = new_amount
                    writer.writerow(new_row)
            else:
                writer.writerow(row)

        return output.getvalue()

    return Response(generate(lines), 
                    mimetype="text/csv",
                    headers={"Content-disposition": "attachment; filename=converted.csv"})

application = app
if __name__ == "__main__":
    application.run()