#include "recordconfiguation.h"
#include "ui_recordconfiguation.h"
#include <iostream>
#include <string>
#include <cstdio>
#pragma comment(lib,"user32")
RecordConfiguation::RecordConfiguation(QWidget *parent) :
    QWidget(parent),
    ui(new Ui::RecordConfiguation)
{
    ui->setupUi(this);
    connect(this, &RecordConfiguation::showEvent, this, &RecordConfiguation::onShowEvent);
}

RecordConfiguation::~RecordConfiguation()
{
    delete ui;
}



void RecordConfiguation::displayListDirectories(const QString& directory){
    QDir dir(directory);
        QStringList dirs = dir.entryList(QDir::Dirs | QDir::NoDotAndDotDot);

        // Clear the existing items in the listWidget
        ui->listWidgetTutorExample->clear();

        for (const QString& dirName : dirs) {
            // Create a new item for each directory
            QListWidgetItem* newItem = new QListWidgetItem(dirName);

            // Set the desired font size for the item
            QFont font = newItem->font();
            font.setPointSize(15);
            newItem->setFont(font);

            // Add the item to the listWidget
            ui->listWidgetTutorExample->addItem(newItem);
        }
}


void RecordConfiguation::showEvent(QShowEvent* event) {
    Q_UNUSED(event);


    displayListDirectories(TutorFolder);
}


void RecordConfiguation::onShowEvent() {
 // Change this to the desired directory
    displayListDirectories(TutorFolder);
}




void RecordConfiguation::on_pushButtonDispaly_clicked()
{
    QListWidgetItem *subdir = ui->listWidgetTutorExample->currentItem();
    if (!subdir) {
        // No item selected, handle this case as needed
        return;
    }

    QString subdir1 = subdir->text();
    QString dir = TutorFolder + subdir1;
    QString program = ".\\videoshow\\dist\\showvideo\\showvideo.exe";

    // Create process
    QProcess *process = new QProcess(this);

    // Connect process signals to slots
    connect(process, SIGNAL(finished(int, QProcess::ExitStatus)), this, SLOT(processFinished(int, QProcess::ExitStatus)));
    connect(process, SIGNAL(errorOccurred(QProcess::ProcessError)), this, SLOT(processError(QProcess::ProcessError)));

    // Start the process
    process->start(program, QStringList() << "--folder" << dir);
    moveWindow(L"Tutor");




}


void RecordConfiguation::on_pushButtonRecord_clicked()
{


    QListWidgetItem *subdir = ui->listWidgetTutorExample->currentItem();
    if (!subdir) {
        // No item selected, handle this case as needed
        return;
    }
    QString subdir1 = subdir->text();
    // Get the current date and time
    QDateTime currentDateTime = QDateTime::currentDateTime();


    QString formattedTime = currentDateTime.toString("yyyy-MM-dd-hh-mm");
    QString dir = RecordingFolder+subdir1+"-follow-"+formattedTime;

    QDir dirname(dir);
    if(!dirname.exists()){
        dirname.mkpath(".");
    }

    QString program = ".\\record\\build\\bin\\Debug\\simple_3d_viewer.exe ";

    QString dir1 = TutorFolder + subdir1;
    QString program1 = ".\\videoshow\\dist\\showvideo\\showvideo.exe";

    // Create process
    QProcess *process = new QProcess(this);
    QProcess *process1 =new QProcess(this);

    // Start the process
    process->start(program, QStringList() << dir);
    moveWindowToRight(L"Color_Image",dir+"\\flag.txt");
    process1->start(program1,QStringList()<< "--folder"<<dir1<<"--mode"<<"withRecording");
    moveWindowToLeft(L"Tutor",dir+"\\flag2.txt");
    // Close the current widget
    close();

}

void RecordConfiguation::moveWindow(const wchar_t* windowName){
    for (int i=0; i<=100; i++){
        HWND hwnd = FindWindow(nullptr, windowName);

        if (hwnd != nullptr) {
            if(IsWindowVisible(hwnd)){
                // Get the screen width
                int screenWidth = GetSystemMetrics(SM_CXSCREEN);
                int screenHeight = GetSystemMetrics(SM_CYSCREEN);

                // Set the new position for the window (adjust the values as needed)
                int newX =0; // move to the right half of the screen
                int newY = screenHeight*1/6;

                // Move the window

                MoveWindow(hwnd, newX, newY, screenWidth, screenHeight*5/6,true);// repaint the window
               // File.remove();
                break;
                }
            else{
                Sleep(100);
            }
        }
        else{
            Sleep(100);
        }
    }
}

void RecordConfiguation::moveWindowToRight(const wchar_t* windowName,QString filename) {
    // Find the window by its name

    QFile File(filename);
    for( int i=0; i<=100; i++){

        if( File.exists()){

            HWND hwnd = FindWindow(nullptr, windowName);

            if (hwnd != nullptr) {
                if(IsWindowVisible(hwnd)){
                    // Get the screen width
                    int screenWidth = GetSystemMetrics(SM_CXSCREEN);
                    int screenHeight = GetSystemMetrics(SM_CYSCREEN);

                    // Set the new position for the window (adjust the values as needed)
                    int newX = screenWidth *3/ 6; // move to the right half of the screen
                    int newY = screenHeight*1/6;

                    // Move the window

                    MoveWindow(hwnd, newX, newY, screenWidth*3 / 6, screenHeight*5/6,true);// repaint the window
                   // File.remove();
                    break;
                    }
            }
            else{
                Sleep(100);
            }

        } else {
            Sleep(100);

        }
    }
}


void RecordConfiguation::moveWindowToLeft(const wchar_t* windowName,QString filename) {
    // Find the window by its name
    qDebug()<<filename;
    QFile File(filename);
    for( int i=0; i<=1500; i++){

        if( File.exists()){

            HWND hwnd = FindWindow(nullptr, windowName);

            if (hwnd != nullptr) {

                    // Get the screen width
                    int screenWidth = GetSystemMetrics(SM_CXSCREEN);
                    int screenHeight = GetSystemMetrics(SM_CYSCREEN);

                    // Set the new position for the window (adjust the values as needed)
                    int newX = 0;
                    int newY = screenHeight*1/6;

                    // Move the window

                    MoveWindow(hwnd, newX, newY, screenWidth*3 / 6, screenHeight*5/6,true);// repaint the window
                   // File.remove();
                    break;

            }
            else
                Sleep(100);

        } else {
            Sleep(100);

        }
    }
}


