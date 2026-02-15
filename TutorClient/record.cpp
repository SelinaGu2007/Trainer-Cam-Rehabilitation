#include "record.h"
#include "ui_record.h"
#pragma comment(lib,"user32")
Record::Record(QWidget *parent) :
    QWidget(parent),
    ui(new Ui::Record)
{
    ui->setupUi(this);
     connect(this, &Record::showEvent, this, &Record::onShowEvent);
}

Record::~Record()
{
    delete ui;
}






void Record::displayListDirectories(const QString& directory){
    QDir dir(directory);
        QStringList dirs = dir.entryList(QDir::Dirs | QDir::NoDotAndDotDot);

        // Clear the existing items in the listWidget
        ui->listWidgetTutorRecording->clear();

        for (const QString& dirName : dirs) {
            // Create a new item for each directory
            QListWidgetItem* newItem = new QListWidgetItem(dirName);

            // Set the desired font size for the item
            QFont font = newItem->font();
            font.setPointSize(15);
            newItem->setFont(font);

            // Add the item to the listWidget
            ui->listWidgetTutorRecording->addItem(newItem);
        }
}

void Record::showEvent(QShowEvent* event) {
    Q_UNUSED(event);

    displayListDirectories(TutorFolder);// Change this to the desired directory
}


void Record::onShowEvent() {
    displayListDirectories(TutorFolder); // Change this to the desired directory
}



void Record::on_pushButtonRecord_clicked()
{

    bool ok;
    QString directoryName = QInputDialog::getText(this, "", "Please Directory Name:", QLineEdit::Normal, "", &ok);
    qDebug()<<directoryName;
    if(!ok |directoryName.isEmpty()){
       return;
    }
    QString directorypath = TutorFolder+directoryName;
     QDir dir(directorypath);
     if(!dir.exists()){
         dir.mkpath(".");
     }
      QString program = ".\\record\\build\\bin\\Debug\\simple_3d_viewer.exe ";
      QProcess *process = new QProcess(this);
      process->start(program, QStringList() << directorypath);
      moveWindowToMiddle(L"Color_Image",directorypath+"\\flag.txt");
      displayListDirectories(TutorFolder);



}

void Record::on_pushButtonDispaly_clicked()
{
    QListWidgetItem *subdir = ui->listWidgetTutorRecording->currentItem();
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
}





void Record::on_pushButtonDelete_clicked()
{
    QListWidgetItem *subdir = ui->listWidgetTutorRecording->currentItem();
    if (!subdir) {
        // No item selected, handle this case as needed
        return;
    }

    QString subdir1 = subdir->text();
    QString dirpath = TutorFolder+subdir1;
    QDir dir(dirpath);

    // Check if the directory exists
    if (!dir.exists()) {
        QMessageBox::warning(this, "Warning", "Directory does not exist!");
        return;
    }

    // Display a confirmation dialog
    QMessageBox::StandardButton reply;
    reply = QMessageBox::question(this, "Confirm Removal", "Are you sure you want to remove the directory at '" + subdir1 + "' and its contents?",
                                  QMessageBox::Yes | QMessageBox::No);

    if (reply == QMessageBox::Yes) {
        // User clicked Yes, so remove the directory and its contents
        if (dir.removeRecursively()) {
            QMessageBox::information(this, "Success", "Directory removed successfully!");
        } else {
            QMessageBox::critical(this, "Error", "Failed to remove directory!");
        }
    }
    displayListDirectories(TutorFolder);
}



void Record::moveWindowToMiddle(const wchar_t* windowName,QString filename) {
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
                    int newX = 0; // move to the right half of the screen
                    int newY = screenHeight*1/4;

                    // Move the window

                    MoveWindow(hwnd, newX, newY, screenWidth, screenHeight*3/4,true);// repaint the window
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
