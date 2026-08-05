#ifndef ASSESSMENTREVIEWDIALOG_H
#define ASSESSMENTREVIEWDIALOG_H

#include <QDialog>
#include <QJsonArray>
#include <QPixmap>

class QLabel;
class QPushButton;
class QScrollArea;
class QSlider;
class QTimer;

class AssessmentReviewDialog : public QDialog
{
public:
    explicit AssessmentReviewDialog(
        const QString &reviewPath,
        const QString &customerFolder,
        const QString &tutorFolder,
        const QString &locale,
        QWidget *parent = nullptr);

    bool isValid() const;

protected:
    void resizeEvent(QResizeEvent *event) override;

private:
    bool loadReview(const QString &reviewPath);
    void buildInterface();
    void showItem(int index);
    void togglePlayback();
    void changeZoom(double delta);
    QString resolveImage(
        const QString &folder, const QString &imageName, int frameIndex) const;
    void updateImageLabels();
    void setImage(QLabel *label, QScrollArea *area, const QPixmap &image);

    QJsonArray Items;
    QString CustomerFolder;
    QString TutorFolder;
    QString Locale;
    int FocusIndex = 0;
    int CurrentIndex = 0;
    double Zoom = 1.0;
    bool Valid = false;
    QLabel *CustomerImage = nullptr;
    QLabel *TutorImage = nullptr;
    QLabel *PositionLabel = nullptr;
    QLabel *IssueLabel = nullptr;
    QLabel *DifferenceLabel = nullptr;
    QScrollArea *CustomerScroll = nullptr;
    QScrollArea *TutorScroll = nullptr;
    QSlider *Timeline = nullptr;
    QPushButton *PlayButton = nullptr;
    QTimer *PlaybackTimer = nullptr;
    QPixmap CustomerPixmap;
    QPixmap TutorPixmap;
};

#endif // ASSESSMENTREVIEWDIALOG_H
