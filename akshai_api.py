#!flask/bin/python
from flask import Flask, jsonify, request
import urllib.request
import os

app = Flask(__name__)


#1Uw93BSs1DSXu8SQeQH4FWraV1ZilgEr9
#curl  http://130.238.29.19:5000/upload_url/<google_drive_fileid>/<filename>/<folder_name>
@app.route('/upload_url/<file_id>/<filename>/<path:folder_name>', methods=['GET'])
def upload_url(file_id,filename,folder_name):
    
    url = "https://docs.google.com/uc?export=download&id=" + file_id
    
    os.system (" hdfs dfs -ls  /" + folder_name + " 2>&1 | tee hdfs.log")
    with open("hdfs.log","r") as f:
        file_read = f.read()
        
        if file_read.find("No such file or directory") != -1:
            os.system("hdfs dfs -mkdir /" + folder_name + " 2>&1 | tee hdfs.log")
            
        if file_read.find(filename) != -1:
            return ("File already exists")

            
    os.system("wget --no-check-certificate '" + url + "' -O - | hdfs dfs -put - /" + folder_name + "/" + filename)
    
    
    return ("Success")



#curl -i -X POST http://130.238.29.19:5000/upload_file -F 'file=@20417.txt.utf-8' -F folder_name=
@app.route('/upload_file', methods=['POST'])
def upload_file():
    
    folder_name = (request.form["folder_name"])

    filename = str(request.files["file"].filename)

    with open('tmp_file.txt', 'wb') as f:
        f.write(request.data)
    
    os.system (" hdfs dfs -put tmp_file.txt " + folder_name + filename + " 2>&1 | tee hdfs.log")
    
    with open("hdfs.log","r") as f:
        file_read = f.read()
        
        if file_read.find("File exists") != -1:
            return ("File already exists")
        
        if file_read.find("No such file or directory") != -1:
            os.system("hdfs dfs -mkdir " + folder_name + " 2>&1 | tee hdfs.log")
            os.system ("hdfs dfs -put tmp_file.txt " + folder_name + filename + " 2>&1 | tee hdfs.log")
            
    os.system("rm tmp_file.txt")
    return ("Success")


#curl  http://130.238.29.19:5000/delete_file/<filename>/<folder_name>
@app.route('/delete_file/<filename>/<path:folder_name>', methods=['GET'])
def delete_file(filename,folder_name):
    
    os.system (" hdfs dfs -ls  /" + folder_name + " 2>&1 | tee hdfs.log")
    
    with open("hdfs.log","r") as f:
        file_read = f.read()
        
        if file_read.find("No such file or directory") != -1:
            return ("Folder name does not exists")
        
        if file_read.find(filename) == -1:
            return ("Filename does not exists")
            
    os.system (" hdfs dfs -rm /" + folder_name + "/" + filename)
        
    return ("Success")


#curl  http://130.238.29.19:5000/delete_folder/<folder_name>
@app.route('/delete_folder/<path:folder_name>', methods=['GET'])
def delete_folder(folder_name):
    
    os.system ("hdfs dfs -ls  /" + folder_name + " 2>&1 | tee hdfs.log")

    with open("hdfs.log","r") as f:
        file_read = f.read()
        
        if file_read.find("No such file or directory") != -1:
            return ("Folder name does not exists")
            
    os.system ("hdfs dfs -rm -r  /" + folder_name)
        
    return ("Success")



if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)
