#include "record.h"
#include "ui_record.h"
#include "appconfig.h"
#include "processwindowtracker.h"

#include <QFileInfo>
#include <QRegularExpression>

#include <exception>

namespace {

QString processDetails(QProcess *process)
{
    return QString::fromUtf8(process->readAllStandardError()).trimmed();
}

bool relativePathEscapesRoot(const QString &relativePath)
{
    return relativePath == ".."
        || relativePath.startsWith("../")
        || relativePath.startsWith("..\\")
        || QDir::isAbsolutePath(relativePath);
}

} // namespace

Record::Record(QWidget *parent) :
    QWidget(parent, Qt::Window),
    ui(new Ui::Record)
{
    ui->setupUi(this);
    const AppConfig &config = AppConfig::instance();
    TutorFolder = config.tutorRecordingsDir;
    RecorderProgram = config.recorderProgram;
    VideoPlayerProgram = config.videoPlayerProgram;
    RecordButtonText = ui->pushButtonRecord->text();
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
    QWidget::showEvent(event);
    displayListDirectories(TutorFolder);// Change this to the desired directory
}


void Record::onShowEvent() {
    displayListDirectories(TutorFolder); // Change this to the desired directory
}



void Record::on_pushButtonRecord_clicked()
{
    if (RecorderProcess && RecorderProcess->state() != QProcess::NotRunning) {
        QMessageBox::information(this, "Recording", "A tutor recording is already running.");
        return;
    }

    bool ok;
    QString directoryName = QInputDialog::getText(this, "", "Please Directory Name:", QLineEdit::Normal, "", &ok);
    directoryName = directoryName.trimmed();
    if (!ok || directoryName.isEmpty()) {
        return;
    }
    static const QRegularExpression validSessionName(
        "^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$");
    if (!validSessionName.match(directoryName).hasMatch()) {
        QMessageBox::warning(
            this,
            "Invalid Recording Name",
            "Use 1-64 letters, numbers, underscores or hyphens.");
        return;
    }

    const QString directoryPath = safeSessionPath(directoryName);
    if (directoryPath.isEmpty()) {
        QMessageBox::critical(
            this,
            "Invalid Recording Path",
            "The recording directory must remain inside the configured tutor folder.");
        return;
    }
    if (QFileInfo::exists(directoryPath)) {
        QMessageBox::warning(
            this,
            "Recording Already Exists",
            "A tutor recording with this name already exists. Please choose a unique name.");
        return;
    }

    const AppConfig &config = AppConfig::instance();
    QString recordingInput = config.captureRecordingPath;
    if (config.captureUsesRecording() && recordingInput.isEmpty()) {
        recordingInput = QFileDialog::getOpenFileName(
            this,
            "Select Azure Kinect recording",
            QString(),
            "Azure Kinect recordings (*.mkv);;All files (*)");
        if (recordingInput.isEmpty()) {
            return;
        }
    }

    QStringList recorderArguments;
    try {
        recorderArguments = config.recorderArguments(directoryPath, recordingInput);
    } catch (const std::exception &error) {
        QMessageBox::critical(this, "Capture source", error.what());
        return;
    }

    auto *process = new QProcess(this);
    RecorderProcess = process;
    setRecordingUi(true);
    process->setProcessChannelMode(QProcess::SeparateChannels);

    connect(process, &QProcess::started, this, [this, process]() {
        trackProcessWindow(
            this,
            process,
            10000,
            ProcessWindowPlacement::LowerThreeQuarters);
    });
    connect(process, &QProcess::errorOccurred, this,
            [this, process](QProcess::ProcessError error) {
        if (error != QProcess::FailedToStart || RecorderProcess != process) {
            return;
        }
        QMessageBox::critical(
            this,
            "Recording Error",
            "Unable to start the Kinect recorder.\n\n" + process->errorString());
        finishRecorderProcess(process);
    });
    connect(process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished),
            this, [this, process, directoryPath](int exitCode, QProcess::ExitStatus exitStatus) {
        if (RecorderProcess != process) {
            process->deleteLater();
            return;
        }

        const bool completionMarkerExists = QFileInfo::exists(
            QDir(directoryPath).filePath("recording.complete"));
        const QString details = processDetails(process);
        const QString suffix = details.isEmpty() ? QString() : "\n\n" + details;
        const bool succeeded = exitStatus == QProcess::NormalExit
            && exitCode == 0
            && completionMarkerExists;

        if (succeeded) {
            QMessageBox::information(
                this,
                "Recording Complete",
                "The tutor recording completed successfully.");
        } else if (exitStatus != QProcess::NormalExit) {
            QMessageBox::critical(
                this,
                "Recording Error",
                "The Kinect recorder stopped unexpectedly." + suffix);
        } else if (exitCode == 10) {
            QMessageBox::warning(
                this,
                "Capture Failed",
                "Kinect capture or body tracking failed before the recording completed." + suffix);
        } else if (exitCode == 2 || exitCode == -1 || exitCode == 255) {
            QMessageBox::critical(
                this,
                "Recording Configuration Error",
                "The recorder received invalid arguments." + suffix);
        } else if (exitCode >= 3 && exitCode <= 9) {
            QMessageBox::critical(
                this,
                "Recording Storage Error",
                "The recorder could not prepare its capture source or output files." + suffix);
        } else if (!completionMarkerExists) {
            QMessageBox::critical(
                this,
                "Incomplete Recording",
                "The recorder exited without writing its completion marker." + suffix);
        } else {
            QMessageBox::critical(
                this,
                "Recording Error",
                "The recorder stopped because of an unexpected error." + suffix);
        }

        if (!succeeded) {
            offerIncompleteRecordingCleanup(directoryPath);
        }
        finishRecorderProcess(process);
    });
    process->start(RecorderProgram, recorderArguments);
}

void Record::on_pushButtonDispaly_clicked()
{
    QListWidgetItem *subdir = ui->listWidgetTutorRecording->currentItem();
    if (!subdir) {
        // No item selected, handle this case as needed
        return;
    }

    QString subdir1 = subdir->text();
    const QString dir = safeSessionPath(subdir1);
    if (dir.isEmpty() || !QDir(dir).exists()) {
        QMessageBox::warning(this, "Playback Error", "The selected recording directory is invalid.");
        return;
    }
    QString program = VideoPlayerProgram;

    // Create process
    QProcess *process = new QProcess(this);

    // Connect process signals to slots
    connect(process, &QProcess::errorOccurred, this, [this, process, program](QProcess::ProcessError error) {
        if (error == QProcess::FailedToStart) {
            QMessageBox::critical(
                this,
                "Playback Error",
                QString("Unable to start the video player: %1\n\n%2")
                    .arg(program, process->errorString()));
            process->deleteLater();
        }
    });
    connect(process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished),
            process, &QObject::deleteLater);

    // Start the process
    process->start(program, QStringList() << "--folder" << dir);
}





void Record::on_pushButtonDelete_clicked()
{
    if (RecorderProcess && RecorderProcess->state() != QProcess::NotRunning) {
        QMessageBox::information(this, "Recording", "Wait for the active recording to finish before deleting sessions.");
        return;
    }

    QListWidgetItem *subdir = ui->listWidgetTutorRecording->currentItem();
    if (!subdir) {
        // No item selected, handle this case as needed
        return;
    }

    QString subdir1 = subdir->text();
    const QString dirpath = safeSessionPath(subdir1);
    if (dirpath.isEmpty()) {
        QMessageBox::critical(
            this,
            "Unsafe Recording Path",
            "The selected directory resolves outside the configured tutor folder and cannot be deleted.");
        return;
    }
    QDir dir(dirpath);

    // Check if the directory exists
    if (!dir.exists()) {
        QMessageBox::warning(this, "Warning", "Directory does not exist!");
        return;
    }

    // Display a confirmation dialog
    const QMessageBox::StandardButton reply = QMessageBox::question(
        this,
        "Confirm Removal",
        "Are you sure you want to remove the directory at '" + subdir1 + "' and its contents?",
        QMessageBox::Yes | QMessageBox::No,
        QMessageBox::No);

    if (reply == QMessageBox::Yes) {
        const QString verifiedPath = safeSessionPath(subdir1);
        if (verifiedPath.isEmpty() || QDir::cleanPath(verifiedPath) != dirpath) {
            QMessageBox::critical(
                this,
                "Unsafe Recording Path",
                "The selected directory changed while awaiting confirmation and cannot be deleted.");
        } else if (QDir(verifiedPath).removeRecursively()) {
            QMessageBox::information(this, "Success", "Directory removed successfully!");
        } else {
            QMessageBox::critical(this, "Error", "Failed to remove directory!");
        }
    }
    displayListDirectories(TutorFolder);
}

QString Record::safeSessionPath(const QString &sessionName) const
{
    const QDir tutorRoot(QDir(TutorFolder).absolutePath());
    const QString targetPath = QDir::cleanPath(tutorRoot.absoluteFilePath(sessionName));
    const QString relativePath = tutorRoot.relativeFilePath(targetPath);
    if (relativePath == "." || relativePathEscapesRoot(relativePath)) {
        return QString();
    }

    const QFileInfo targetInfo(targetPath);
    if (targetInfo.exists()) {
        const QString canonicalRoot = QFileInfo(tutorRoot.absolutePath()).canonicalFilePath();
        const QString canonicalTarget = targetInfo.canonicalFilePath();
        if (canonicalRoot.isEmpty() || canonicalTarget.isEmpty()) {
            return QString();
        }
        const QString canonicalRelative = QDir(canonicalRoot).relativeFilePath(canonicalTarget);
        if (canonicalRelative == "." || relativePathEscapesRoot(canonicalRelative)) {
            return QString();
        }
    }
    return targetPath;
}

void Record::setRecordingUi(bool recording)
{
    ui->pushButtonRecord->setEnabled(!recording);
    ui->pushButtonDelete->setEnabled(!recording);
    ui->pushButtonRecord->setText(recording ? "Recording..." : RecordButtonText);
}

void Record::finishRecorderProcess(QProcess *process)
{
    if (RecorderProcess != process) {
        return;
    }
    RecorderProcess = nullptr;
    setRecordingUi(false);
    displayListDirectories(TutorFolder);
    process->deleteLater();
}

void Record::offerIncompleteRecordingCleanup(const QString &directoryPath)
{
    if (!QDir(directoryPath).exists()) {
        return;
    }

    const QString sessionName = QFileInfo(directoryPath).fileName();
    const QString verifiedPath = safeSessionPath(sessionName);
    if (verifiedPath.isEmpty()
        || QDir::cleanPath(verifiedPath) != QDir::cleanPath(directoryPath)) {
        QMessageBox::critical(
            this,
            "Cleanup Error",
            "The incomplete recording path can no longer be verified safely.");
        return;
    }

    const QMessageBox::StandardButton reply = QMessageBox::question(
        this,
        "Incomplete Recording",
        "The recording directory contains incomplete data. Remove it now?",
        QMessageBox::Yes | QMessageBox::No,
        QMessageBox::No);
    if (reply == QMessageBox::Yes && !QDir(verifiedPath).removeRecursively()) {
        QMessageBox::critical(
            this,
            "Cleanup Error",
            "Unable to remove the incomplete recording directory.");
    }
}
