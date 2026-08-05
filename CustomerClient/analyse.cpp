#include "analyse.h"
#include "ui_analyse.h"
#include "appconfig.h"
#include "assessmentresultdialog.h"

#include <QFile>
#include <QFileInfo>
#include <QTimer>

#include <string>

#pragma comment(lib,"user32")

Analyse::Analyse(QWidget *parent) :
    QWidget(parent),
    ui(new Ui::Analyse)
{
    ui->setupUi(this);
    const AppConfig &config = AppConfig::instance();
    TutorFolder = config.tutorRecordingsDir;
    MyRecordingFolder = config.customerRecordingsDir;
    AnalyzerProgram = config.analyzerProgram;
    AnalyzerPrefixArguments = config.analyzerPrefixArguments;
    ExerciseProfile = config.exerciseProfile;
    SubjectTrackingConfig = config.subjectTrackingConfig;
    FeedbackLocale = config.feedbackLocale;
    VoiceFeedbackEnabled = config.voiceFeedbackEnabled;
    VoiceRate = config.voiceRate;
    VoiceVolume = config.voiceVolume;
    FeedbackTimer = new QTimer(this);
    FeedbackTimer->setInterval(200);
    connect(FeedbackTimer, &QTimer::timeout, this, &Analyse::tryShowFeedback);
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



    QString folder_tutor = QDir(TutorFolder).filePath(subdir1);
    QString folder_customer = QDir(MyRecordingFolder).filePath(subdir2);
    QString dir1 = QDir::toNativeSeparators(folder_tutor); // Ensure correct path separators
    QString dir2 = QDir::toNativeSeparators(folder_customer); // Ensure correct path separators

    QString program = AnalyzerProgram;
    const QString assessmentPath = QDir(folder_customer).filePath("assessment.json");
    const QString feedbackPath = QDir(folder_customer).filePath("feedback_summary.json");
    QFile::remove(assessmentPath);
    QFile::remove(feedbackPath);
    QStringList arguments = AnalyzerPrefixArguments;
    arguments << "--folder_tutor" << dir1
              << "--folder_customer" << dir2
              << "--profile" << ExerciseProfile
              << "--tracking-config" << SubjectTrackingConfig
              << "--report-output" << assessmentPath
              << "--feedback-output" << feedbackPath
              << "--feedback-locale" << FeedbackLocale
              << "--function" << "showVideos";



    QProcess *process = new QProcess(this);
    ui->pushButtonAnalyse->setEnabled(false);
    startFeedbackPolling(feedbackPath);
    process->setProcessChannelMode(QProcess::SeparateChannels);
    connect(process, &QProcess::errorOccurred, this, [this, program](QProcess::ProcessError error) {
        FeedbackTimer->stop();
        ui->pushButtonAnalyse->setEnabled(true);
        QMessageBox::critical(
            this, "Analysis Error",
            QString("Unable to start the motion analyzer: %1\nError code: %2")
                .arg(program).arg(static_cast<int>(error)));
    });
    connect(process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished),
            this, [this, process](int exitCode, QProcess::ExitStatus exitStatus) {
        ui->pushButtonAnalyse->setEnabled(true);
        if (exitStatus != QProcess::NormalExit || exitCode != 0) {
            FeedbackTimer->stop();
            const QString details = QString::fromUtf8(process->readAllStandardError()).trimmed();
            QMessageBox::warning(
                this, "Session Quality Check",
                "Motion analysis stopped because the recording did not pass its quality checks."
                + (details.isEmpty() ? QString() : "\n\n" + details));
        }
        process->deleteLater();
    });
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
    QString dirpath = QDir(MyRecordingFolder).filePath(subdir1);
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
    auto *timer = new QTimer(this);
    timer->setInterval(100);
    timer->setProperty("attempts", 0);
    const std::wstring title(windowName);
    connect(timer, &QTimer::timeout, this, [timer, title, dirname]() {
        const int attempts = timer->property("attempts").toInt() + 1;
        timer->setProperty("attempts", attempts);
        QDir directory(dirname);
        if (directory.exists() && !directory.isEmpty()) {
            HWND hwnd = FindWindow(nullptr, title.c_str());
            if (hwnd != nullptr) {
                const int screenWidth = GetSystemMetrics(SM_CXSCREEN);
                const int screenHeight = GetSystemMetrics(SM_CYSCREEN);
                MoveWindow(hwnd, 0, screenHeight / 6, screenWidth, screenHeight * 5 / 6, true);
                timer->stop();
                timer->deleteLater();
                return;
            }
        }
        if (attempts >= 1500) {
            timer->stop();
            timer->deleteLater();
        }
    });
    timer->start();
}

void Analyse::startFeedbackPolling(const QString &feedbackPath)
{
    PendingFeedbackPath = feedbackPath;
    FeedbackPollAttempts = 0;
    FeedbackTimer->start();
}

void Analyse::tryShowFeedback()
{
    ++FeedbackPollAttempts;
    if (QFileInfo::exists(PendingFeedbackPath)) {
        auto *dialog = new AssessmentResultDialog(
            PendingFeedbackPath,
            VoiceFeedbackEnabled,
            VoiceRate,
            VoiceVolume,
            this);
        if (dialog->isValid()) {
            FeedbackTimer->stop();
            dialog->setAttribute(Qt::WA_DeleteOnClose);
            dialog->show();
            dialog->raise();
            dialog->activateWindow();
            return;
        }
        dialog->deleteLater();
    }
    if (FeedbackPollAttempts >= 1500) {
        FeedbackTimer->stop();
        QMessageBox::warning(
            this,
            "Assessment Result",
            "The assessment completed without a readable feedback summary.");
    }
}


