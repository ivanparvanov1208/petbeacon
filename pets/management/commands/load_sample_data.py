from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile
from pets.models import (
    Pet, Vaccination, MedicalRecord, Medication, VetVisit, Reminder,
    Consultation, ConsultationMessage,
)
from datetime import date, timedelta


class Command(BaseCommand):
    help = "Loads sample demo data for PetBeacon application"

    def handle(self, *args, **options):
        self.stdout.write("[PetBeacon] Resetting accounts to the two demo users...")
        User.objects.exclude(username__in=["demo_owner", "demo_vet"]).delete()
        demo_user, created = User.objects.get_or_create(
            username="demo_owner",
            defaults={
                "email": "demo@petcare.bg",
                "first_name": "Елена",
                "last_name": "Димитрова",
            }
        )
        demo_user.set_password("demo12345")
        demo_user.first_name = "Елена"
        demo_user.last_name = "Димитрова"
        demo_user.email = "owner@petbeacon.demo"
        demo_user.is_staff = False
        demo_user.is_superuser = False
        demo_user.save()

        profile, _ = UserProfile.objects.get_or_create(user=demo_user)
        profile.role = UserProfile.ROLE_OWNER
        profile.phone = "+359 88 765 4321"
        profile.city = "София"
        profile.save()

        demo_vet, _ = User.objects.get_or_create(
            username="demo_vet",
            defaults={
                "email": "vet@petbeacon.demo",
                "first_name": "Николай",
                "last_name": "Тодоров",
            },
        )
        demo_vet.set_password("VetDemo123!")
        demo_vet.email = "vet@petbeacon.demo"
        demo_vet.first_name = "Николай"
        demo_vet.last_name = "Тодоров"
        demo_vet.is_staff = False
        demo_vet.is_superuser = False
        demo_vet.save()
        vet_profile, _ = UserProfile.objects.get_or_create(user=demo_vet)
        vet_profile.role = UserProfile.ROLE_VET
        vet_profile.phone = "+359 2 987 6543"
        vet_profile.city = "София"
        vet_profile.save()

        today = date.today()

        self.stdout.write("[PetBeacon] Clearing previous pets and reminders for demo user...")
        Pet.objects.filter(owner=demo_user).delete()
        Reminder.objects.filter(owner=demo_user).delete()
        Pet.objects.filter(owner=demo_vet).delete()
        Reminder.objects.filter(owner=demo_vet).delete()
        Consultation.objects.filter(owner__in=[demo_user, demo_vet]).delete()
        Consultation.objects.filter(veterinarian__in=[demo_user, demo_vet]).delete()

        self.stdout.write("[PetBeacon] Creating Pet 1: Rex...")
        rex = Pet.objects.create(
            owner=demo_user,
            name="Рекс",
            species="dog",
            breed="Немска овчарка",
            gender="male",
            is_neutered=True,
            birth_date=today - timedelta(days=365 * 2 + 180),
            weight=32.50,
            microchip_number="642098100123456",
            passport_number="BG 0482910",
            food_diet="Суха храна висок клас (Royal Canin Maxi Adult), 380 грама на ден, разделени на 2 приема (сутрин в 8:00 и вечер в 19:00). Като награда обича варени моркови и ябълки.",
            allergies="Няма установени хранителни алергии.",
            special_notes="Много енергичен и умен. Обича да носи топки за тенис и да плува в реката. Има навика да лае по звънеца на вратата."
        )

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

        self.stdout.write("[PetBeacon] Creating Pet 2: Maya...")
        maya = Pet.objects.create(
            owner=demo_user,
            name="Мая",
            species="cat",
            breed="Британска късокосместа",
            gender="female",
            is_neutered=True,
            birth_date=today - timedelta(days=365 + 150),
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

        self.stdout.write("[PetBeacon] Creating Pet 3: Charlie...")
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

        self.stdout.write("[PetBeacon] Creating vet clinic patient records...")
        luna = Pet.objects.create(
            owner=demo_vet,
            name="Луна",
            species="dog",
            breed="Лабрадор ретривър",
            gender="female",
            is_neutered=True,
            birth_date=today - timedelta(days=365 * 4),
            weight=27.40,
            microchip_number="642098100765432",
            passport_number="BG 0614820",
            allergies="Чувствителност към говежди протеин.",
            special_notes="Пациент на ВетСити. Собственикът съобщава за сезонен сърбеж.",
        )
        VetVisit.objects.create(
            pet=luna,
            visit_date=today - timedelta(days=3),
            clinic_name="Ветеринарна клиника ВетСити",
            vet_name="Д-р Николай Тодоров",
            phone="+359 2 987 6543",
            reason="Контролен преглед за кожно раздразнение",
            examination_summary="Леко зачервяване по корема, общото състояние е добро.",
            recommendations="Контрол след 14 дни; избягване на нова храна до контролния преглед.",
            total_cost=65.00,
        )
        MedicalRecord.objects.create(
            pet=luna,
            date=today - timedelta(days=3),
            title="Дерматологичен контролен преглед",
            diagnosis="Лек сезонен дерматит; няма признаци за вторична инфекция.",
            treatment="Измиване с ветеринарен шампоан два пъти седмично за 2 седмици.",
            veterinarian="Д-р Николай Тодоров",
            clinic="Ветеринарна клиника ВетСити",
            cost=65.00,
            notes="Алергията към говежди протеин е отбелязана в досието.",
        )
        Vaccination.objects.create(
            pet=luna,
            name="Годишна поливалентна ваксина",
            date_administered=today - timedelta(days=355),
            next_due_date=today + timedelta(days=10),
            batch_number="DH-2026-1842",
            clinic_or_vet="Д-р Николай Тодоров · ВетСити",
            notes="Без нежелани реакции.",
        )
        Medication.objects.create(
            pet=luna,
            name="Омега-3 ветеринарна добавка",
            dosage="1 капсула",
            frequency="Веднъж дневно с храната",
            start_date=today - timedelta(days=3),
            end_date=today + timedelta(days=11),
            instructions="Да се приема с основното хранене.",
            is_active=True,
            notes="Кратък курс до контролния преглед.",
        )
        Reminder.objects.create(
            owner=demo_vet,
            pet=luna,
            reminder_type="vet_visit",
            title="Контролен преглед на Луна",
            due_date=today + timedelta(days=11),
            due_time="11:00",
            priority="high",
            notes="Проследяване на кожното раздразнение и поносимостта към режима.",
        )

        milo = Pet.objects.create(
            owner=demo_vet,
            name="Мило",
            species="cat",
            breed="Европейска късокосместа",
            gender="male",
            is_neutered=True,
            birth_date=today - timedelta(days=365 * 7),
            weight=5.10,
            microchip_number="642098100234567",
            allergies="Не са известни.",
            special_notes="Нужен е ежегоден контрол на зъбите и теглото.",
        )
        VetVisit.objects.create(
            pet=milo,
            visit_date=today - timedelta(days=21),
            clinic_name="Ветеринарна клиника ВетСити",
            vet_name="Д-р Николай Тодоров",
            phone="+359 2 987 6543",
            reason="Годишен профилактичен преглед",
            examination_summary="Стабилно общо състояние; препоръчано е проследяване на теглото.",
            recommendations="Контролно претегляне след 30 дни и постепенно намаляване на лакомствата.",
            total_cost=45.00,
        )
        Reminder.objects.create(
            owner=demo_vet,
            pet=milo,
            reminder_type="vet_visit",
            title="Контролно претегляне на Мило",
            due_date=today + timedelta(days=9),
            priority="normal",
            notes="Сравнете теглото с последния профилактичен преглед.",
        )

        demo_chat = Consultation.objects.create(
            owner=demo_user,
            veterinarian=demo_vet,
            pet=rex,
            subject="Рекс се чеше след разходка",
            initial_message="От вчера Рекс се чеше по корема след разходка в парка. Няма промяна в храната и се храни нормално. Има ли нещо, което да следя?",
            status=Consultation.STATUS_OPEN,
            payment_status=Consultation.PAYMENT_COMPED,
            listed_price_cents=1000,
        )
        ConsultationMessage.objects.create(
            consultation=demo_chat,
            sender=demo_vet,
            body="Благодаря за описанието. Проверете дали има зачервяване или подуване и изпратете снимка, ако се появи. Ако сърбежът се усили или Рекс стане отпаднал, уговорете преглед.",
        )
        ConsultationMessage.objects.create(
            consultation=demo_chat,
            sender=demo_user,
            body="Разгледах кожата и има само леко зачервяване. Ще наблюдавам и ще пиша отново утре.",
        )

        self.stdout.write(self.style.SUCCESS("[PetBeacon] Sample data created successfully!"))
        self.stdout.write(self.style.SUCCESS("[PetBeacon] Owner: demo_owner | Password: demo12345"))
        self.stdout.write(self.style.SUCCESS("[PetBeacon] Vet: demo_vet | Password: VetDemo123!"))
