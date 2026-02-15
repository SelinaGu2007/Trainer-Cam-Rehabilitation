#include "analyse.h"
#include "ui_analyse.h"

#pragma comment(lib,"user32")

Analyse::Analyse(QWidget *parent) :
    QWidget(parent),
    ui(new Ui::Analyse)
{
    ui->setupUi(this);
    connect(this,&Analyse::showEvent,this,&Analyse::onShowEvent1);
}

Analyse::~Analyse()
{
    delete ui;
}








void Analyse::displayListDirectories1(const QString& directory){
    QDir dir(directory);
        QStringList dirs = dir.entryList(QDir::Dirs | QDir::NoDotAndDotDot);

        // Clear the existing items in the listWidget
        ui->listWidgetTask->clear();

        for (const QString& dirName : dirs) {
            // Create a new item for each directory
            QListWidgetItem* newItem = new QListWidgetItem(dirName);

            // Set the desired font size for the item
            QFont font = newItem->font();
            font.setPointSize(15);
            newItem->setFont(font);

            // Add the item to the listWidget
            ui->listWidgetTask->addItem(newItem);
        }
}



void Analyse::onShowEvent1() {
    displayListDirectories1(MyRecordingFolder); // Change this to the desired directory
}

void Analyse::showEvent(QShowEvent* event) {
    Q_UNUSED(event);

    displayListDirectories1(MyRecordingFolder); // Change this to the desired directory
}

void Analyse::on_pushButtonAnalyse_clicked()
{

    QListWidgetItem *subdir = ui->listWidgetTask->currentItem();
    if (!subdir) {
        // No item selected, handle this case as needed
        return;
    }

    QString subdir2 = subdir->text();
    QString subdir1 = subdir2.section('-', 0, 0);



    QString folder_tutor = TutorFolder+subdir1;
    QString folder_customer = MyRecordingFolder+subdir2;
    QString dir1 = QDir::toNativeSeparators(folder_tutor); // Ensure correct path separators
    QString dir2 = QDir::toNativeSeparators(folder_customer); // Ensure correct path separators

    QString program = ".\\test_exe\\dist\\main\\main.exe";
    QStringList arguments;
    arguments << "--folder_tutor" << dir1 << "--folder_customer" << dir2 << "--function" << "showVideos";



    QProcess *process = new QProcess(this);
    process->start(program, arguments);

    moveWindowAnalyse(L"Ananlse_outcome",dir2+"//analyse");



}


void Analyse::on_pushButtonDelete_clicked()
{
    QListWidgetItem *subdir = ui->listWidgetTask->currentItem();
    if (!subdir) {
        // No item selected, handle this case as needed
        return;
    }

    QString subdir1 = subdir->text();
    QString dirpath = MyRecordingFolder+subdir1;
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

     displayListDirectories1(MyRecordingFolder);
}

void Analyse::moveWindowAnalyse(const wchar_t* windowName,QString dirname){

    QDir Dir(dirname);
    for( int i=0; i<=1500; i++){

        if( Dir.exists()){
            if(!Dir.isEmpty()){
                HWND hwnd = FindWindow(nullptr, windowName);
                if (hwnd != nullptr) {
                        // Get the screen width
                        int screenWidth = GetSystemMetrics(SM_CXSCREEN);
                        int screenHeight = GetSystemMetrics(SM_CYSCREEN);

                        // Set the new position for the window (adjust the values as needed)
                        int newX = 0;
                        int newY = screenHeight*1/6;


                        MoveWindow(hwnd, newX, newY, screenWidth, screenHeight*5/6,true);// repaint the window
                       // File.remove();
                        break;

                  }
                else{
                    Sleep(100);
                }

            }
            else
                Sleep(100);

        } else {
            Sleep(100);

        }
    }

}


