#include "login.h"
#include "ui_login.h"
#include <QMessageBox>
Login::Login(QWidget *parent) :
    QDialog(parent),
    ui(new Ui::Login)
{
    ui->setupUi(this);
}

Login::~Login()
{
    delete ui;
}

void Login::on_pushButtonConfirm_clicked()
{
    QString username = ui->lineEditUsername->text();
    QString password = ui->lineEditPassword->text();
    if(username=="gsl" & password=="123"){
            accept();
    }
    else{
        QMessageBox::critical(this,"error","username or password wrong");
        ui->lineEditUsername->clear();
        ui->lineEditPassword->clear();
    }
}

