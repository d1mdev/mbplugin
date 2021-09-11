# Автоматический контроль баланса сотовых операторов и не только их

## Возможности программы MBplugin

На текущий момент самостоятельное приложение (Windows Linux и MacOs.), позволяющее автоматизировать получение балансов МТС, Билайн, Мегафон, Теле2, Yota(modem), Ростелеком, ОнЛайм, Zadarma, Cardtel, SipNet, Карта стрелка, Автодор транспондер, Московский паркинг, Мосэнергосбыт, курсы валют и акций, список операторов пополняется.  
Изначально была написана как надстройка для MobileBalance и такой вариант работы также возможен.  
В инструкции вариант использования без MobileBalance называется **standalone**.  
Интерфейс программы организован в виде внутреннего веб сервера.  
Умеет отправлять полученные балансы в телеграм, также через телеграм бота можно производить запросы по телефонам.  
Для работы с личными кабинетами используется где это возможно API и простые запросы. В сложных случаях (коих как показала практика большинство) используется библиотека [playwright-python](https://github.com/microsoft/playwright-python)

## Инструкцию по настройке в режиме самостоятельной программы смотрите в standalone.md 
Полное отсутствие ограничений, накладываемых лицензией mobilebalance, можно проверять любое количество телефонов.  
[Инструкция по варианту использования standalone](https://github.com/artyl/mbplugin/blob/master/standalone.md)

## Инструкцию по настройке в режиме мега-плагина для программы MobileBalance смотрите в mobilebalance.md 
[Инструкция по варианту использования mobilebalance](https://github.com/artyl/mbplugin/blob/master/mobilebalance.md)

## На данный момент реализованы плагины

(Источником информации послужили как собственное изучение так и существующие плагины, так что, пользуясь случаем, хочу выразить благодарность всем авторам:
leha3d, Pasha, comprech, y-greek и другим, кто тратил свои силы и время на реверс сайтов операторов и разработку)  
mts - МТС (сотовая связь)  
beeline - Билайн (сотовая связь)  
megafon - Мегафон (сотовая связь)  
megafonb2b - Мегафон b2b (сотовая связь)  
tele2 - ТЕЛЕ2 (сотовая связь)  
yota - Yota (сотовая связь)  
a1by - A1(velcom) Беларусь (сотовая связь)  
rostelecom - Ростелеком (телефония и интернет)  
smile-net - Infoline/smile-net/Virgin connect (Интернет провайдер)  
onlime - onlime.ru (Интернет провайдер)  
lovit - lovit.ru (Интернет провайдер)  
zadarma - Zadarma.com (IP телефония)  
cardtel - Cardtel (IP телефония)  
sipnet - Sipnet (IP телефония)  
strelka - Баланс карты стрелка  
sodexo - Получение баланса карты Sodexo (подарочные карты)  
currency - Курсы валют USD, EUR, с ЦБ и с MOEX, курсы акций с MOEX и yahoo finance (заменил плагины eur, usd, moex и yahoo)
stock - Расчет цены портфеля ценных бумаг  
avtodor-tr - Автодор транспондер  
parking_mos - parking.mos.ru оплата парковки (Вход через логин/пароль на login.mos.ru)  
mosenergosbyt - Сайт мосэнергосбыт (ЖКХ)  
vscale - Облачные серверы для разработчиков  
Для плагинов rostelecom и mosenergosbyt можно указывать конкретный лицевой счет если их несколько в формате ```login/лицевой_счет```  

### Тестовые плагины
test1 - Простой тест с демонстрацией всех полей (на нем хорошо видно что из DLL плагина прихолят не все поля)  
test2 - Пример реализации ввода капчи через tix/tkinter  
test3 - Пример реализации проверки через браузер (playwright)  
test4 - Пример ручной реализации проверки через браузер (playwright)  


