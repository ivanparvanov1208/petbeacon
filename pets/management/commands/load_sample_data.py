from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile
from pets.models import Pet, Vaccination, MedicalRecord, Medication, VetVisit, Reminder
from datetime import date, timedelta


class Command(BaseCommand):
    help = "Loads sample demo data for VetLink application"

    def handle(self, *args, **options):
        self.stdout.write("[VetLink] Creating / updating demo user...")
        demo_user, created = User.objects.get_or_create(
            username="demo_owner",
            defaults={
                "email": "demo@petcare.bg",
                "first_name": "Елена",
                "last_name": "Димитрова",
                "is_staff": True,
                "is_superuser": True,
            }
        )
        demo_user.set_password("demo12345")
        demo_user.first_name = "Елена"
        demo_user.last_name = "Димитрова"
        demo_user.is_staff = True
        demo_user.is_superuser = True
        demo_user.save()

        profile, _ = UserProfile.objects.get_or_create(user=demo_user)
        profile.role = UserProfile.ROLE_OWNER
        profile.phone = "+359 88 765 4321"
        profile.city = "София"
        profile.save()

        today = date.today()

        self.stdout.write("[VetLink] Clearing previous pets and reminders for demo user...")
        Pet.objects.filter(owner=demo_user).delete()
        Reminder.objects.filter(owner=demo_user).delete()

        # 1. Куче Рекс
        self.stdout.write("[VetLink] Creating Pet 1: Rex...")
        rex = Pet.objects.create(
            owner=demo_user,
            name="Рекс",
            species="dog",
            breed="Немска овчарка",
            gender="male",
            is_neutered=True,
            birth_date=today - timedelta(days=365 * 2 + 180),  # approx 2.5 yrs
            weight=32.50,
            microchip_number="642098100123456",
            passport_number="BG 0482910",
            food_diet="Суха храна висок клас (Royal Canin Maxi Adult), 380 грама на ден, разделени на 2 приема (сутрин в 8:00 и вечер в 19:00). Като награда обича варени моркови и ябълки.",
            allergies="Няма установени хранителни алергии.",
            special_notes="Много енергичен и умен. Обича да носи топки за тенис и да плува в реката. Има навика да лае по звънеца на вратата."
        )

        # Рекс - Ваксинации
        Vaccination.objects.create(
            pet=rex,
            name="Годишна поливалентна DHPPi+L",
            date_administered=today - timedelta(days=355),
            next_due_date=today + timedelta(days=10),
            batch_number="DH-2023-9981A",
            clinic_or_vet='ВетСити София - Д-р Тодоров',
            notes="Без странични реакции. Понесена нормално."
        )
        Vaccination.objects.create(
            pet=rex,
            name="Ваксина срещу Бяс (Rabisin)",
            date_administered=today - timedelta(days=355),
            next_due_date=today + timedelta(days=10),
            batch_number="RAB-44510",
            clinic_or_vet='ВетСити София - Д-р Тодоров',
            notes="Вписана в европейския паспорт."
        )
        Vaccination.objects.create(
            pet=rex,
            name="Ваксина срещу Кашлица (Nobivac KC)",
            date_administered=today - timedelta(days=120),
            next_due_date=today + timedelta(days=245),
            batch_number="KC-88124",
            clinic_or_vet='ВетСити София - Д-р Тодоров',
            notes="Интраназално приложение."
        )

        # Рекс - Медицински записи
        MedicalRecord.objects.create(
            pet=rex,
            date=today - timedelta(days=45),
            title="Травма на лапата след скок",
            diagnosis="Леко разтягане на сухожилието на предна дясна лапа. Рентгенографията не показва фрактури.",
            treatment="Покой за 7 дни. Прием на противовъзпалително (Римодил) за 5 дни.",
            veterinarian="Д-р Димитрова",
            clinic="Ветеринарна клиника 'ВетСити'",
            cost=85.00,
            notes="Възстановяването премина отлично, кучето отново тича без накуцване."
        )
        MedicalRecord.objects.create(
            pet=rex,
            date=today - timedelta(days=210),
            title="Почистване на зъбен камък с ултразвук",
            diagnosis="Зъбен камък по кътниците и лек гингивит.",
            treatment="Почистване с ултразвуков скалер и полиране с паста.",
            veterinarian="Д-р Тодоров",
            clinic="Ветеринарна клиника 'ВетСити'",
            cost=120.00,
            notes="Препоръчани дентални лакомства 2 пъти седмично."
        )

        # Рекс - Медикаменти
        Medication.objects.create(
            pet=rex,
            name="АртроВет Комплекс (глюкозамин за стави)",
            dosage="1 таблетка дневно",
            frequency="Веднъж на ден, сутрин",
            start_date=today - timedelta(days=30),
            end_date=today + timedelta(days=60),
            instructions="Да се дава по време на хранене или увита в парченце сирене.",
            is_active=True,
            notes="Профилактичен курс за едри породи кучета."
        )

        # Рекс - Ветеринарни посещения
        VetVisit.objects.create(
            pet=rex,
            visit_date=today - timedelta(days=45),
            clinic_name="Ветеринарна клиника 'ВетСити'",
            vet_name="Д-р Димитрова",
            phone="+359 2 987 6543",
            reason="Накуцване с предна дясна лапа след игра в парка",
            examination_summary="Папация показа чувствителност в областта на китката. Няма оток.",
            recommendations="Ограничаване на тичането за 1 седмица. Студени компреси първите 24 часа.",
            total_cost=85.00
        )

        # Рекс - Напомняния
        Reminder.objects.create(
            owner=demo_user,
            pet=rex,
            reminder_type="vaccination",
            title="Годишна ваксинация (Бяс + DHPPi)",
            due_date=today + timedelta(days=10),
            due_time="10:30",
            priority="high",
            notes="Запазен час във ВетСити при д-р Тодоров."
        )
        Reminder.objects.create(
            owner=demo_user,
            pet=rex,
            reminder_type="deworming",
            title="Вътрешно обезпаразитяване с Дронтал Плюс",
            due_date=today + timedelta(days=1),
            priority="normal",
            notes="3 таблетки и половина според теглото от 32.5 кг."
        )

        # 2. Котка Мая
        self.stdout.write("[VetLink] Creating Pet 2: Maya...")
        maya = Pet.objects.create(
            owner=demo_user,
            name="Мая",
            species="cat",
            breed="Британска късокосместа",
            gender="female",
            is_neutered=True,
            birth_date=today - timedelta(days=365 + 150),  # approx 1.4 yrs
            weight=4.20,
            microchip_number="642098100876543",
            passport_number="BG 0591234",
            food_diet="Сутрин и вечер: 1/2 пауч качествена мокра храна (Schesir с риба тон). Суха храна за кастрирани котки на разположение. Воден фонтан за постоянна свежа вода.",
            allergies="Лека чувствителност към пилешко месо.",
            special_notes="Много спокойна и гальовна, обича да спи на най-високия рафт на котешкото дърво. Не понася прахосмукачката."
        )

        Vaccination.objects.create(
            pet=maya,
            name="Purevax RCP (панлевкопения, калицивирус, херпесвирус)",
            date_administered=today - timedelta(days=180),
            next_due_date=today + timedelta(days=185),
            batch_number="PVX-10928B",
            clinic_or_vet='Централна Ветеринарна Клиника',
            notes="Отлична поносимост."
        )

        Medication.objects.create(
            pet=maya,
            name="Малт паста за отвеждане на косми (GimCat)",
            dosage="3-4 см лентичка",
            frequency="През ден",
            start_date=today - timedelta(days=60),
            instructions="Директно от тубата или върху лапичката.",
            is_active=True,
            notes="Предотвратява образуването на космени топки в стомаха."
        )

        VetVisit.objects.create(
            pet=maya,
            visit_date=today - timedelta(days=220),
            clinic_name="Централна Ветеринарна Клиника",
            vet_name="Д-р Ангелова",
            phone="+359 2 816 4500",
            reason="Стерилизация и поставяне на микрочип",
            examination_summary="Успешна операция, бързо излизане от упойка.",
            recommendations="Следене на шевовете 10 дни, носене на предпазна якичка.",
            total_cost=210.00
        )

        Reminder.objects.create(
            owner=demo_user,
            pet=maya,
            reminder_type="medication",
            title="Външно обезпаразитяване с капки Broadline",
            due_date=today + timedelta(days=4),
            priority="normal",
            notes="Нанасяне на холката след разресване."
        )
        Reminder.objects.create(
            owner=demo_user,
            pet=maya,
            reminder_type="food_refill",
            title="Поръчка на котешка храна и пясък",
            due_date=today + timedelta(days=6),
            priority="low",
            notes="Бентонит пясък с аромат на лавандула + паучове."
        )

        # 3. Папагал Чарли
        self.stdout.write("[VetLink] Creating Pet 3: Charlie...")
        charlie = Pet.objects.create(
            owner=demo_user,
            name="Чарли",
            species="bird",
            breed="Корела (Нимфа)",
            gender="male",
            is_neutered=False,
            approximate_age="1 година",
            weight=0.09,
            food_diet="Специална зърнена смеска за средни папагали Prestige, пресни резени ябълка, моркови, спанак и сепийна кост за калций.",
            allergies="Авокадо, шоколад и лук са строго забранени (токсични за птици!).",
            special_notes="Много музикален, подсвирква мелодии от филми и казва 'Здрасти Чарли'. Обича да стои на рамото."
        )

        VetVisit.objects.create(
            pet=charlie,
            visit_date=today - timedelta(days=90),
            clinic_name="Екзотик Вет София",
            vet_name="Д-р Маринов",
            phone="+359 878 112233",
            reason="Профилактичен преглед на перата и човката",
            examination_summary="Отлично оперение, чисто дишане, човката е в нормално състояние.",
            recommendations="Да продължи с плодово-зеленчуковата добавка към диетата.",
            total_cost=40.00
        )

        Reminder.objects.create(
            owner=demo_user,
            pet=charlie,
            reminder_type="grooming",
            title="Основно почистване и дезинфекция на волиерата",
            due_date=today + timedelta(days=2),
            priority="normal",
            notes="Измиване на кацалките с топла вода и подмяна на пясъчното дъно."
        )

        Reminder.objects.create(
            owner=demo_user,
            pet=rex,
            reminder_type="vet_visit",
            title="Контролен преглед на лапата на Рекс",
            due_date=today - timedelta(days=14),
            is_completed=True,
            notes="Прегледът мина супер, всичко е наред."
        )

        self.stdout.write(self.style.SUCCESS("[VetLink] Sample data created successfully!"))
        self.stdout.write(self.style.SUCCESS("[VetLink] Demo Username: demo_owner | Password: demo12345"))
