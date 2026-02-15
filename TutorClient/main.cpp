#include "mainwindow.h"

#include <QApplication>
#include "login.h"
int main(int argc, char *argv[])
{
    QApplication a(argc, argv);
    Login *login =new Login;
    if(login->exec() == QDialog::Accepted){
        MainWindow w;
        w.showMaximized();
        return a.exec();
    }
}
