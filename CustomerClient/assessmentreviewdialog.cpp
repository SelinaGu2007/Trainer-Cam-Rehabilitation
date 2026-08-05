#include "assessmentreviewdialog.h"

#include <QDialogButtonBox>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QFont>
#include <QHBoxLayout>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QPushButton>
#include <QResizeEvent>
#include <QScrollArea>
#include <QSlider>
#include <QTimer>
#include <QVBoxLayout>

AssessmentReviewDialog::AssessmentReviewDialog(
    const QString &reviewPath,
    const QString &customerFolder,
    const QString &tutorFolder,
    const QString &locale,
    QWidget *parent)
    : QDialog(parent),
      CustomerFolder(QDir(customerFolder).absolutePath()),
      TutorFolder(QDir(tutorFolder).absolutePath()),
      Locale(locale)
{
    Valid = loadReview(reviewPath);
    if (Valid) {
        buildInterface();
    }
}

bool AssessmentReviewDialog::isValid() const
{
    return Valid;
}

bool AssessmentReviewDialog::loadReview(const QString &reviewPath)
{
    QFile file(reviewPath);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        return false;
    }
    QJsonParseError error;
    const QJsonDocument document = QJsonDocument::fromJson(file.readAll(), &error);
    if (error.error != QJsonParseError::NoError || !document.isObject()) {
        return false;
    }
    const QJsonObject root = document.object();
    if (root.value("format").toString() != "trainercam.session-review"
        || root.value("schema_version").toInt() != 1) {
        return false;
    }
    Items = root.value("items").toArray();
    if (Items.isEmpty() || root.value("item_count").toInt() != Items.size()) {
        return false;
    }
    const QJsonObject worst = root.value("worst_segment").toObject();
    FocusIndex = qBound(0, worst.value("focus_index").toInt(), Items.size() - 1);
    return true;
}

void AssessmentReviewDialog::buildInterface()
{
    const bool chinese = Locale == "zh-CN";
    setWindowTitle(chinese ? QStringLiteral("动作回看") : QStringLiteral("Movement Review"));
    resize(1120, 760);
    setMinimumSize(800, 620);
    setModal(false);

    auto *layout = new QVBoxLayout(this);
    layout->setContentsMargins(20, 16, 20, 16);
    layout->setSpacing(10);

    auto *title = new QLabel(
        chinese ? QStringLiteral("用户动作与示范动作对照")
                : QStringLiteral("Your movement compared with the demonstration"),
        this);
    QFont titleFont = title->font();
    titleFont.setPointSize(17);
    titleFont.setBold(true);
    title->setFont(titleFont);
    layout->addWidget(title);

    auto *imageLayout = new QHBoxLayout();
    auto createImagePanel = [this, imageLayout](
                                const QString &caption, QLabel **image, QScrollArea **scroll) {
        auto *panel = new QVBoxLayout();
        auto *label = new QLabel(caption, this);
        QFont captionFont = label->font();
        captionFont.setPointSize(12);
        captionFont.setBold(true);
        label->setFont(captionFont);
        panel->addWidget(label);

        *image = new QLabel(this);
        (*image)->setAlignment(Qt::AlignCenter);
        (*image)->setMinimumSize(320, 280);
        (*image)->setStyleSheet("background: #151515; color: white;");
        *scroll = new QScrollArea(this);
        (*scroll)->setAlignment(Qt::AlignCenter);
        (*scroll)->setWidget(*image);
        (*scroll)->setWidgetResizable(false);
        panel->addWidget(*scroll, 1);
        imageLayout->addLayout(panel, 1);
    };
    createImagePanel(
        chinese ? QStringLiteral("示范动作") : QStringLiteral("Demonstration"),
        &TutorImage,
        &TutorScroll);
    createImagePanel(
        chinese ? QStringLiteral("你的动作") : QStringLiteral("Your movement"),
        &CustomerImage,
        &CustomerScroll);
    layout->addLayout(imageLayout, 1);

    PositionLabel = new QLabel(this);
    DifferenceLabel = new QLabel(this);
    IssueLabel = new QLabel(this);
    IssueLabel->setWordWrap(true);
    QFont issueFont = IssueLabel->font();
    issueFont.setPointSize(12);
    issueFont.setBold(true);
    IssueLabel->setFont(issueFont);
    layout->addWidget(PositionLabel);
    layout->addWidget(DifferenceLabel);
    layout->addWidget(IssueLabel);

    Timeline = new QSlider(Qt::Horizontal, this);
    Timeline->setRange(0, Items.size() - 1);
    Timeline->setAccessibleName(
        chinese ? QStringLiteral("动作回看时间轴") : QStringLiteral("Movement review timeline"));
    connect(Timeline, &QSlider::valueChanged, this, [this](int value) { showItem(value); });
    layout->addWidget(Timeline);

    auto *controls = new QHBoxLayout();
    auto *previous = new QPushButton(chinese ? QStringLiteral("上一帧") : QStringLiteral("Previous"), this);
    PlayButton = new QPushButton(chinese ? QStringLiteral("播放") : QStringLiteral("Play"), this);
    auto *next = new QPushButton(chinese ? QStringLiteral("下一帧") : QStringLiteral("Next"), this);
    auto *focus = new QPushButton(
        chinese ? QStringLiteral("跳到重点问题") : QStringLiteral("Jump to key issue"), this);
    auto *zoomOut = new QPushButton(QStringLiteral("−"), this);
    auto *zoomIn = new QPushButton(QStringLiteral("+"), this);
    zoomOut->setAccessibleName(chinese ? QStringLiteral("缩小") : QStringLiteral("Zoom out"));
    zoomIn->setAccessibleName(chinese ? QStringLiteral("放大") : QStringLiteral("Zoom in"));
    connect(previous, &QPushButton::clicked, this, [this]() {
        Timeline->setValue(qMax(0, CurrentIndex - 1));
    });
    connect(next, &QPushButton::clicked, this, [this]() {
        Timeline->setValue(qMin(Items.size() - 1, CurrentIndex + 1));
    });
    connect(PlayButton, &QPushButton::clicked, this, [this]() { togglePlayback(); });
    connect(focus, &QPushButton::clicked, this, [this]() { Timeline->setValue(FocusIndex); });
    connect(zoomOut, &QPushButton::clicked, this, [this]() { changeZoom(-0.25); });
    connect(zoomIn, &QPushButton::clicked, this, [this]() { changeZoom(0.25); });
    controls->addWidget(previous);
    controls->addWidget(PlayButton);
    controls->addWidget(next);
    controls->addWidget(focus);
    controls->addStretch();
    controls->addWidget(zoomOut);
    controls->addWidget(zoomIn);
    layout->addLayout(controls);

    auto *disclaimer = new QLabel(
        chinese
            ? QStringLiteral("逐帧差异属于训练辅助工程反馈，不是医学诊断。")
            : QStringLiteral("Frame differences are engineering exercise feedback, not a medical diagnosis."),
        this);
    disclaimer->setWordWrap(true);
    disclaimer->setStyleSheet("color: #555; font-size: 10pt;");
    layout->addWidget(disclaimer);

    auto *buttons = new QDialogButtonBox(QDialogButtonBox::Close, this);
    connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::close);
    layout->addWidget(buttons);

    PlaybackTimer = new QTimer(this);
    PlaybackTimer->setInterval(150);
    connect(PlaybackTimer, &QTimer::timeout, this, [this]() {
        if (CurrentIndex >= Items.size() - 1) {
            PlaybackTimer->stop();
            PlayButton->setText(Locale == "zh-CN" ? QStringLiteral("播放") : QStringLiteral("Play"));
            return;
        }
        Timeline->setValue(CurrentIndex + 1);
    });

    Timeline->setValue(FocusIndex);
    showItem(FocusIndex);
}

QString AssessmentReviewDialog::resolveImage(
    const QString &folder, const QString &imageName, int frameIndex) const
{
    const QString base = QDir(folder).absolutePath();
    const QStringList candidates = {
        imageName,
        QString("image_idx_%1.jpg").arg(frameIndex),
        QString("imamge_idx_%1.jpg").arg(frameIndex)
    };
    for (const QString &candidate : candidates) {
        if (candidate.trimmed().isEmpty()) {
            continue;
        }
        const QString absolute = QFileInfo(QDir(base).filePath(candidate)).absoluteFilePath();
        const QString relative = QDir(base).relativeFilePath(absolute);
        if (QDir::isAbsolutePath(relative)
            || relative == ".."
            || relative.startsWith("../")
            || relative.startsWith("..\\")) {
            continue;
        }
        const QFileInfo info(absolute);
        if (info.exists() && info.isFile()) {
            return info.absoluteFilePath();
        }
    }
    return QString();
}

void AssessmentReviewDialog::showItem(int index)
{
    if (!Valid || index < 0 || index >= Items.size()) {
        return;
    }
    CurrentIndex = index;
    const QJsonObject item = Items.at(index).toObject();
    const QJsonObject customer = item.value("customer").toObject();
    const QJsonObject tutor = item.value("tutor").toObject();
    const QJsonObject issue = item.value("issue").toObject();
    const bool chinese = Locale == "zh-CN";

    const QString customerPath = resolveImage(
        CustomerFolder,
        customer.value("image").toString(),
        customer.value("frame_index").toInt());
    const QString tutorPath = resolveImage(
        TutorFolder,
        tutor.value("image").toString(),
        tutor.value("frame_index").toInt());
    CustomerPixmap = customerPath.isEmpty() ? QPixmap() : QPixmap(customerPath);
    TutorPixmap = tutorPath.isEmpty() ? QPixmap() : QPixmap(tutorPath);
    updateImageLabels();

    PositionLabel->setText(
        chinese
            ? QStringLiteral("对齐位置 %1 / %2 · 用户原始帧 %3 · 示范原始帧 %4")
                  .arg(index + 1)
                  .arg(Items.size())
                  .arg(customer.value("frame_index").toInt())
                  .arg(tutor.value("frame_index").toInt())
            : QStringLiteral("Aligned position %1 of %2 · your frame %3 · demonstration frame %4")
                  .arg(index + 1)
                  .arg(Items.size())
                  .arg(customer.value("frame_index").toInt())
                  .arg(tutor.value("frame_index").toInt()));
    const double difference = item.value("difference_deg").toDouble();
    DifferenceLabel->setText(
        chinese ? QStringLiteral("综合角度差：%1°").arg(difference, 0, 'f', 1)
                : QStringLiteral("Combined angle difference: %1°").arg(difference, 0, 'f', 1));

    const QString severity = issue.value("severity").toString();
    const QString colour = severity == "review" ? "#a12622" : severity == "adjust" ? "#a46400" : "#237a3b";
    const QString message = issue.value("message").toString();
    const QString keyPrefix = item.value("in_worst_segment").toBool()
                                  ? (chinese ? QStringLiteral("重点阶段 · ") : QStringLiteral("Key segment · "))
                                  : QString();
    IssueLabel->setText(
        keyPrefix + issue.value("label").toString()
        + QStringLiteral(" — %1°").arg(issue.value("error_deg").toDouble(), 0, 'f', 1)
        + (message.isEmpty() ? QString() : QStringLiteral("\n") + message));
    IssueLabel->setStyleSheet("color: " + colour + ";");
}

void AssessmentReviewDialog::togglePlayback()
{
    const bool chinese = Locale == "zh-CN";
    if (PlaybackTimer->isActive()) {
        PlaybackTimer->stop();
        PlayButton->setText(chinese ? QStringLiteral("播放") : QStringLiteral("Play"));
        return;
    }
    if (CurrentIndex >= Items.size() - 1) {
        Timeline->setValue(0);
    }
    PlaybackTimer->start();
    PlayButton->setText(chinese ? QStringLiteral("暂停") : QStringLiteral("Pause"));
}

void AssessmentReviewDialog::changeZoom(double delta)
{
    Zoom = qBound(0.5, Zoom + delta, 3.0);
    updateImageLabels();
}

void AssessmentReviewDialog::setImage(
    QLabel *label, QScrollArea *area, const QPixmap &image)
{
    if (image.isNull()) {
        label->setPixmap(QPixmap());
        label->resize(qMax(320, area->viewport()->width()), qMax(280, area->viewport()->height()));
        label->setText(Locale == "zh-CN" ? QStringLiteral("此帧没有可用图像")
                                          : QStringLiteral("No image is available for this frame"));
        return;
    }
    label->setText(QString());
    const QSize viewport = area->viewport()->size();
    const QSize target(
        qMax(1, static_cast<int>(viewport.width() * Zoom)),
        qMax(1, static_cast<int>(viewport.height() * Zoom)));
    const QPixmap scaled = image.scaled(target, Qt::KeepAspectRatio, Qt::SmoothTransformation);
    label->setPixmap(scaled);
    label->resize(scaled.size());
}

void AssessmentReviewDialog::updateImageLabels()
{
    if (!CustomerImage || !TutorImage) {
        return;
    }
    setImage(CustomerImage, CustomerScroll, CustomerPixmap);
    setImage(TutorImage, TutorScroll, TutorPixmap);
}

void AssessmentReviewDialog::resizeEvent(QResizeEvent *event)
{
    QDialog::resizeEvent(event);
    updateImageLabels();
}
