"""Bind the foundation sequence and missing sources to existing learning hours.

Run after review_task_hours.py and before render_courses.py/render_timeline.py.
This script changes content and evidence, never task hours or trial counts.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATE = '2026-11-11'


def bi(ru, en):
    return {'ru': ru, 'en': en}


def main():
    literature = json.loads((ROOT / 'literature.json').read_text())
    estimate = json.loads((ROOT / 'estimate.json').read_text())
    courses = json.loads((ROOT / 'courses.json').read_text())
    before_hours = {k: [(t['learn'], t['build'], t['verify']) for t in estimate['items'][k]['tasks']]
                    for k in estimate['order']}

    additions = [
        ('SW13', 'Fusion: выбранный AHRS без магнитометра', 'Fusion: selected no-magnetometer AHRS',
         'x-io Technologies', 'https://github.com/xioTechnologies/Fusion', ['M11'],
         'README: AHRS algorithm, settings, outputs, bias; Examples/Python/simple_example.py. Освоить один алгоритм на IMU M06, затем тот же C-компонент. На границе адаптера переводить рад/с в град/с и м/с² в g; внутри проекта сохранять SI. Зафиксировать проверенную версию.',
         'README AHRS algorithm/settings/outputs/bias and Examples/Python/simple_example.py. Use one algorithm on the M06 IMU, then the same C component. Convert rad/s to degrees/s and m/s² to g only at the adapter; retain SI in the project. Pin the tested version.',
         'Готовый фильтр не определяет параметры калибровки датчика. Без магнитометра абсолютный курс не становится наблюдаемым.',
         'The filter does not determine sensor calibration parameters. Without a magnetometer, absolute heading is not observable.'),
        ('SW14', 'OpenCV: поза камеры и пиксель → известная плоскость', 'OpenCV: camera pose and pixel → known plane',
         'OpenCV contributors', 'https://docs.opencv.org/4.6.0/d5/d1f/calib3d_solvePnP.html', ['M14'],
         'Основной путь: solvePnP по мишени с известными координатами в системе основания → undistortPoints → луч камеры → пересечение с известной плоскостью. Гомография — необязательное альтернативное объяснение одной плоскости, не вторая реализация.',
         'Primary path: solvePnP from a target with known base-frame coordinates → undistortPoints → camera ray → known-plane intersection. Homography is an optional single-plane explanation, not a second implementation.',
         'Плоскость и высота целевой точки должны быть известны; произвольная глубина из одного пикселя не восстанавливается. Hand–eye для камеры на руке — дальнейшее развитие.',
         'The target plane and point height must be known; arbitrary depth is not recovered from one pixel. Eye-in-hand calibration is further development.'),
        ('math-contact', 'Underactuated Robotics: контакт и многозвенная динамика', 'Underactuated Robotics: contact and multibody dynamics',
         'Russ Tedrake, MIT', 'https://underactuated.mit.edu/multibody.html', ['D2','M13','M19'],
         'Simple Double Pendulum; The Dynamics of Contact; Compliant Contact Models; начало Time-stepping Approximations. Вывод своей 2R-модели, затем смысл силы, импульса, трения и жёсткости. Полный LCP-решатель не реализуется.',
         'Simple Double Pendulum; The Dynamics of Contact; Compliant Contact Models; introduction to Time-stepping Approximations. Derive a 2R model, then interpret force, impulse, friction and stiffness. Do not implement a full LCP solver.',
         'Учебные модели требуют проверки геометрии и параметров; параметры физического движка сами по себе не подтверждают модель.',
         'Teaching models require geometry/parameter validation; physics-engine settings alone do not validate a model.'),
        ('math-qp', 'CVXPY: квадратичная задача и статус решения', 'CVXPY: quadratic program and solution status',
         'CVXPY authors', 'https://www.cvxpy.org/examples/basic/quadratic_program.html', ['M19'],
         'Стандартная форма QP, положительно полуопределённая матрица, равенства и неравенства; затем собственная плоская задача двух опор. Проверять problem.status, невязки и ограничения вне решателя.',
         'Standard QP form, positive-semidefinite matrix, equality/inequality constraints; then the custom planar two-support problem. Check problem.status, residuals and constraints independently of the solver.',
         'Библиотечный пример объясняет интерфейс, но не задаёт физические ограничения робота. Плоская статическая QP не является контактной динамикой или WBC.',
         'The library example explains the interface, not robot constraints. A planar static QP is neither contact dynamics nor WBC.'),
        ('H-GAIT', 'OpenSHC: квазистатические многоногие походки', 'OpenSHC: quasi-static multilegged gaits',
         'Benjamin Tam, Fletcher Talbot, Ryan Steindl, Alberto Elfes, Navinda Kottege', 'https://arxiv.org/abs/2006.04424', ['M19','M22','M23'],
         'Из статьи выбрать кинематику, позу корпуса, генерацию траектории стопы, фазы походки и переходы. Воспроизвести один цикл crawl и фазовые таблицы wave/ripple на своей геометрии. Не переносить весь чужой стек.',
         'Select kinematics, body pose, foot trajectory generation, gait phases and transitions. Reproduce one crawl cycle and wave/ripple phase tables on the custom geometry; do not port the entire external stack.',
         'Это сравнительный исследовательский пример; совместимость кода с Jazzy и характеристики своего робота проверяются отдельно.',
         'This is a comparative research example; Jazzy code compatibility and custom robot performance require separate checks.'),
        ('H-TENDON-FRICTION', 'Трение и потери натяжения в тросовой передаче', 'Friction and tension loss in tendon transmission',
         'Yang Liu and Farshid Alambeigi', 'https://pmc.ncbi.nlm.nih.gov/articles/PMC9415037/', ['T1','T2'],
         'Impact of Generic Tendon Routing on Tension Loss, IEEE RA-L 2022: постановка, физический смысл потерь и экспериментальные кривые натяжения при тяге/отпускании. Сопоставить с одной собственной петлёй; полный Cosserat-решатель не требуется.',
         'Impact of Generic Tendon Routing on Tension Loss, IEEE RA-L 2022: problem, physical meaning of losses and experimental pulling/releasing tension curves. Compare with one custom loop; a full Cosserat solver is not required.',
         'Медицинская геометрия статьи не подтверждает печатный хвост. Измерять собственные трение, упругость, преднатяг и связь секций. Прямой доступ PMC иногда требует проверки браузера; DOI — альтернативный вход.',
         'The medical geometry does not validate a printed tail. Measure custom friction, elasticity, pretension and section coupling. PMC may challenge browser access; DOI is an alternative entry point.'),
    ]
    refs = {r['id']: r for r in literature['references']}
    for key, ru, en, author, url, stages, sr, se, lr, le in additions:
        entry = {'id': key, 'title': bi(ru,en), 'authors': author,
                 'edition': bi('Материал проверен 11.11.2026; фиксировать используемую версию/редакцию.', 'Checked 11 November 2026; record the version/edition used.'),
                 'access': bi('Бесплатный первичный онлайн-источник.', 'Free primary online source.'),
                 'url': url, 'stages': stages, 'group': 'hardware' if key.startswith('H-') else 'math' if key.startswith('math-') else 'software',
                 'role': 'core_selected', 'selection': bi(sr,se), 'limitations': bi(lr,le), 'links': [],
                 'status': bi('Открытое содержание первичного источника проверено; аппаратная совместимость не испытана.', 'Public primary-source content checked; hardware compatibility not tested.')}
        if key == 'H-TENDON-FRICTION':
            entry['links'] = [{'title':'Published article DOI','url':'https://doi.org/10.1109/LRA.2022.3147903'}]
            entry['status'] = bi('Проверено индексированное содержание авторской статьи в PMC; прямое открытие возвращало проверку браузера.', 'Indexed primary article content checked; direct opening returned a browser challenge.')
        if key == 'SW13':
            entry['links'] = [{'title':'Official no-magnetometer example','url':'https://github.com/xioTechnologies/Fusion/blob/main/Examples/Python/simple_example.py'}]
        if key == 'SW14':
            entry['links'] = [{'title':'Optional homography explanation','url':'https://docs.opencv.org/4.6.0/d9/dab/tutorial_homography.html'}]
        if key in refs:
            refs[key].update(entry)
        else:
            literature['references'].append(entry)
            refs[key] = entry

    refs['math-feedback']['selection'] = bi('По заданиям D2/M10/M11: определения модели состояния, линеаризации, полюсов, устойчивости и наблюдаемости; PID и цифровая реализация. Для M10-F — запасы главы 10 и неопределённость из начала главы 13. Конкретные часы и выбранные фрагменты указаны в блоках заданий.',
        'Task-specific D2/M10/M11 selections: state model, linearization, poles, stability, observability, PID and digital implementation. M10-F adds chapter 10 margins and chapter 13 uncertainty introduction. Task units specify hours and excerpts.')
    refs['math-modern-robotics']['selection'] = bi('Связанные определения глав 2–6: конфигурация, движения, FK/IK, якобиан и статика; выбранные разделы 8–12: динамика, временная траектория, планирование, управление и контакт. По каждому этапу назначается конкретная задача, не полное чтение всех глав.',
        'Connected definitions from chapters 2–6: configuration, motions, FK/IK, Jacobian and statics; selections from 8–12: dynamics, time trajectories, planning, control and contact. Each stage assigns a specific problem, not full chapter reading.')
    refs['H-SLOCUM']['selection'] = bi('M05/D1/A1: нужные части тем 4 и 8–10 о механизмах, конструкциях, соединениях и опорах. T1/T2: добавить выбранные части тем 5–6 о шкивах, барабанах, кабелях и передаче мощности; capstan применять только с его предположениями.',
        'M05/D1/A1: relevant parts of topics 4 and 8–10 on mechanisms, structures, connections and supports. T1/T2 add selected topics 5–6 on pulleys, drums, cables and power transmission; apply capstan only under its assumptions.')

    def reading(stage, ref, ru, en):
        route = literature['routes'][stage]
        entry = next((r for r in route['readings'] if r['ref'] == ref), None)
        if entry:
            entry['selection'] = bi(ru,en)
        else:
            route['readings'].append({'ref':ref,'selection':bi(ru,en)})

    reading('M02','math-modern-robotics','Глава 2: конфигурация, степени свободы, рабочее и конфигурационное пространство; начало главы 3: точка, направление, вращение и перенос. Связать с ручным 2R-примером, не изучать весь аппарат Lie-групп до первой ноги.',
            'Chapter 2: configuration, DOF, workspace and C-space; beginning of chapter 3: points, directions, rotation and translation. Use a hand-worked 2R example; no full Lie-group treatment before the first leg.')
    reading('M08','math-modern-robotics','Связная последовательность: выбранные определения главы 3 → FK главы 4 → позиционный якобиан/статика главы 5 → IK главы 6. Для своей ноги вывести FK/IK и J, затем объяснить сингулярность. Сравнение всех DH/PoE-представлений не назначается.',
            'Connected sequence: selected chapter 3 definitions → chapter 4 FK → chapter 5 positional Jacobian/statics → chapter 6 IK. Derive custom leg FK/IK/J and explain singularity; no exhaustive DH/PoE comparison.')
    reading('D2','math-contact','Simple Double Pendulum: вывести свою плоскую 2R-модель через энергию, выделить M(q), C(q,q̇), g(q), записать состояние и линеаризацию около равновесия. Проверить по энергии и независимой библиотеке. Это конкретная двухзвенная задача, не полный вывод динамики руки.',
            'Simple Double Pendulum: derive the custom planar 2R energy model, identify M(q), C(q,q̇), g(q), state and equilibrium linearization. Check energy and an independent library; this is one two-link problem, not full arm dynamics.')
    reading('M10','math-feedback','Нужные определения глав 3, 5–8: состояние, равновесие, линеаризация, полюса, устойчивость и наблюдаемость на модели D2. Глава 11 — PID/насыщение/цифровая реализация. Для M10-F — глава 10: запасы и задержка; начало главы 13: неопределённость и условия робастности. Разделы назначены по заданиям ниже, не целыми главами.',
            'Needed definitions from chapters 3 and 5–8: state, equilibrium, linearization, poles, stability and observability on D2. Chapter 11: PID, saturation, digital implementation. M10-F: chapter 10 margins/delay and chapter 13 introduction to uncertainty/robustness. Task-specific selections below, not entire chapters.')
    reading('M11','SW13',*tuple(refs['SW13']['selection'][x] for x in ('ru','en')))
    reading('M11','math-feedback','Глава 8: наблюдаемость и оценивание; объяснить, почему наклон и абсолютный курс имеют разные ограничения. Использовать уже полученную модель состояния D2.',
            'Chapter 8: observability and estimation; explain differing limits for inclination and absolute heading using the D2 state model.')
    reading('M11','math-labbe','Глава 04: один скалярный ручной predict/update и смысл ковариации/невязки. Он объясняет оценивание, но не создаёт второй полный фильтр вместо выбранного Fusion.',
            'Chapter 04: one scalar hand-worked predict/update and covariance/innovation meaning. This explains estimation without creating a second full filter alongside Fusion.')
    reading('M13','math-contact','The Dynamics of Contact и Compliant Contact Models; введение в time stepping. Для M13.5: сила/импульс, нормальная реакция, статическое/динамическое трение, проникновение, жёсткость и dt. Потом проверить эти понятия в уже выбранном Gazebo.',
            'The Dynamics of Contact, Compliant Contact Models and introduction to time stepping. M13.5 covers force/impulse, normal force, static/dynamic friction, penetration, stiffness and dt; test these in the existing Gazebo setup.')
    reading('M14','SW14',*tuple(refs['SW14']['selection'][x] for x in ('ru','en')))
    reading('M16','math-modern-robotics','Глава 9: путь и траектория, временное масштабирование и ограничения скорости/ускорения; глава 10: смысл пространства конфигураций, коллизий и одного планировщика. Один ручной профиль, затем готовые инструменты MoveIt.',
            'Chapter 9: path versus trajectory, time scaling and velocity/acceleration limits; chapter 10: C-space, collisions and one planner. One hand-worked profile, then existing MoveIt tools.')
    reading('M19','H-GAIT',*tuple(refs['H-GAIT']['selection'][x] for x in ('ru','en')))
    reading('M19','math-qp',*tuple(refs['math-qp']['selection'][x] for x in ('ru','en')))
    reading('M19','math-convex','Только постановка выпуклой квадратичной задачи с линейными ограничениями и смысл допустимости; использовать в уже заданной плоской задаче двух опор. Полный Boyd не назначается.',
            'Only convex QP formulation with linear constraints and feasibility, applied to the existing planar two-support problem; not the full Boyd text.')
    reading('M19','math-tedrake','Simple Legs — краткое сравнение опоры/переноса и динамической ходьбы. Основной источник многоногих фаз — H-GAIT; Simple Legs не считается готовым рецептом crawl.',
            'Simple Legs briefly contrasts stance/swing and dynamic walking. H-GAIT is the main multilegged phase source; Simple Legs is not treated as a ready-made crawl recipe.')
    for stage in ('M22','M23'):
        reading(stage,'H-GAIT','Повторно использовать фазовые диаграммы и траектории M19; перед физическим запуском проверить свою геометрию, допустимые опоры, переходы и остановку. Новый контроллер из чужого репозитория не устанавливается.',
                'Reuse M19 phase diagrams and trajectories; verify custom geometry, feasible supports, transitions and stopping before hardware runs. Do not install another external controller.')
    for stage in ('T1','T2'):
        reading(stage,'H-TENDON-FRICTION',*tuple(refs['H-TENDON-FRICTION']['selection'][x] for x in ('ru','en')))
    reading('T1','H-SLOCUM','Темы 5–6: свой шкив/барабан, кабельная передача, радиус, момент и capstan при проскальзывании; темы 8–10: опоры и жёсткость. Ограничение по трению выводить с указанием режима, затем измерять реальную петлю.',
            'Topics 5–6: actual pulley/drum, cable transmission, radius, torque and capstan in sliding; topics 8–10: supports/stiffness. State the friction regime and measure the actual loop.')
    reading('T2','H-RAO','Из §5 выбрать вес и внешнюю нагрузку, влияние жёсткости и связь секций. Сопоставить с собственными измерениями. Трение/растяжение не считать закрытыми этой статьёй: для них H-TENDON-FRICTION и протокол в learning-guides.md.',
            'Select gravity/load, stiffness and segment coupling from section 5 and compare with measurements. Do not treat this article as covering friction/extension; use H-TENDON-FRICTION and the learning-guides.md protocol.')

    # Each entry occupies existing learning time; practice/evidence use its
    # existing task. No second lab or full book is silently added.
    focus = {
        'M02.2': ('math-strang,math-modern-robotics', 'Конфигурация и DOF; точка/вектор, базис, вращение и плечо силы на 2R-геометрии.', 'Configuration/DOF, point/vector, frame, rotation and lever arm on 2R geometry.'),
        'M08.1': ('math-modern-robotics', 'Связать определения движений с реальными осями CAD и преобразованиями своей ноги.', 'Connect rigid-motion definitions to actual CAD axes and leg transforms.'),
        'D2.1': ('math-modern-robotics,math-feedback', 'Энергия одной оси → уравнение → состояние → равновесие и локальная линеаризация.', 'Single-axis energy → equation → state → equilibrium and local linearization.'),
        'D2.2': ('math-contact,math-modern-robotics', 'Своя 2R-динамика через T−U; матрица инерции, связь звеньев и гравитация; независимый библиотечный эталон.', 'Own 2R dynamics from T−U; inertia matrix, link coupling and gravity; independent library reference.'),
        'M10.1': ('math-feedback', 'По модели D2 объяснить полюса и устойчивость, затем PID/PD и насыщение; один ручной пример.', 'Explain poles/stability from D2, then PID/PD and saturation, with one hand-worked example.'),
        'M10.6': ('math-feedback', 'FBS 10: запасы/задержка; FBS 13: неопределённость и границы вывода. Один контур и интервалы параметров.', 'FBS 10 margins/delay; FBS 13 uncertainty and inference limits, on one loop with parameter intervals.'),
        'M11.1': ('SW13,math-modern-robotics', 'Оси, quaternion и единицы; SI-контракт и явный адаптер Fusion (град/с, g).', 'Axes, quaternion and units; SI contract and explicit Fusion adapter (degrees/s, g).'),
        'M11.2': ('SW13,math-feedback', 'Fusion без магнитометра: интегрирование гироскопа, коррекция наклона, gain, ускорение и фиксированная версия.', 'No-magnetometer Fusion: gyro integration, tilt correction, gain, acceleration and pinned version.'),
        'M11.3': ('SW13', 'Независимый эталон наклона, дрейф курса, движение и линейное ускорение; качество и ограничения оценки.', 'Independent tilt reference, heading drift, motion/linear acceleration, estimate quality and limits.'),
        'M11.4': ('math-feedback,math-labbe', 'Наблюдаемость на знакомой модели; один скалярный шаг KF и смысл невязки, без второго AHRS.', 'Observability on the familiar model; one scalar KF step and innovation meaning, without a second AHRS.'),
        'M13.5': ('math-contact,SW03', 'Сила против импульса; нормальная реакция, трение, податливый/жёсткий контакт и шаг расчёта; один простой эталон.', 'Force versus impulse, normal force, friction, compliant/rigid contact and timestep; one simple reference.'),
        'M14.1': ('SW05,SW14', 'Восемь часов: 3 на модель/дисторсию, 2 на позу камеры по мишени, 3 на луч–плоскость и системы координат. Одна процедура.', 'Eight hours: 3 camera/distortion, 2 target-based camera pose, 3 ray–plane and frames. One procedure.'),
        'M14.3': ('SW14,math-modern-robotics', 'Из нормализованного луча получить точку в системе основания; известная высота, параллельный луч и неверная плоскость.', 'Map a normalized ray to a base-frame point; known height, parallel ray and wrong-plane cases.'),
        'M16.2': ('SW04,SW07,math-modern-robotics', 'C-space и коллизии; объяснить один RRT/PRM и отказ пути, затем настроить один готовый планировщик.', 'C-space/collisions; explain one RRT/PRM and path failure, then configure one existing planner.'),
        'M16.3': ('math-modern-robotics,SW04', 'Путь против траектории; один профиль временного масштабирования и физические пределы, затем параметризация MoveIt.', 'Path versus trajectory; one time-scaling profile and physical limits, then MoveIt parameterization.'),
        'M19.3': ('H-GAIT,math-modern-robotics', 'Один цикл crawl: диаграмма опоры/переноса, duty factor, COM и разрешение LIFT; сопоставить с собственной моделью.', 'One crawl cycle: stance/swing diagram, duty factor, COM and LIFT permission on the custom model.'),
        'M19.5': ('H-GAIT,math-modern-robotics', 'Неподвижные стопы, поза корпуса и допустимые реакции опор; объяснить отличие статического запаса от динамической гарантии.', 'Stationary feet, body pose and feasible contact forces; distinguish static margin from dynamic guarantees.'),
        'M19.7': ('math-qp,math-convex,math-modern-robotics', 'Семь часов: 2 форма QP/выпуклость, 2 баланс и трение двух опор, 1 API/статус, 2 ручной эталон и ограничения.', 'Seven hours: 2 QP/convexity, 2 two-support balance/friction, 1 API/status, 2 manual reference and constraints.'),
        'T1.1': ('H-OCR,H-RAO', 'Кинематика постоянной кривизны и её допущения; вес и самонесение рассматривать отдельно от красивой формы.', 'Constant-curvature kinematics and assumptions; distinguish gravity/self-support from nominal shape.'),
        'T1.2': ('H-ROY,H-SLOCUM,H-RAO', 'Три хребта: жёсткость и прогиб от собственного веса, масса, закрепление и повторяемость разгрузки.', 'Three backbones: stiffness/self-weight sag, mass, mounting and unloading repeatability.'),
        'T1.3': ('H-SLOCUM,H-TENDON-FRICTION', 'Радиус/момент, capstan и режим скольжения, натяжение/растяжение, обратный ход; протокол собственной петли.', 'Radius/torque, capstan and sliding regime, tension/extension, reversal; custom-loop protocol.'),
        'T2.1': ('H-IDF,H-DRIVES,H-TENDON-FRICTION', 'Первое активное управление с преднатягом; пределы натяжения, калибровка нуля и измеренная нагрузка.', 'First active pretensioned section: tension limits, zero calibration and measured loading.'),
        'T2.2': ('H-RAO,H-TENDON-FRICTION', 'Как дальние тросы нагружают ближние секции; закрепления и связь секций своей компоновки.', 'How distal tendons load proximal sections; routing and coupling of the custom layout.'),
        'T2.3': ('H-TENDON-FRICTION,H-RAO', 'Кривые тяга/отпускание и повтор под нагрузкой; простая таблица/модель с направлением и историей; независимая проверка.', 'Pull/release curves and loaded repeat; simple direction/history-aware map/model with independent validation.'),
        'M23.3': ('H-GAIT,math-modern-robotics', 'Wave/ripple на готовом crawl: фазовые таблицы, доля опоры и разрешённые переходы.', 'Wave/ripple on existing crawl: phase tables, duty factor and allowed transitions.'),
    }
    # Add references needed by per-task units without assigning full extra books.
    for stage, ref in [('D2','math-feedback'),('M11','math-modern-robotics'),('M14','math-modern-robotics'),('T1','H-ROY'),('M23','math-modern-robotics')]:
        if not any(r['ref'] == ref for r in literature['routes'][stage]['readings']):
            reading(stage,ref,'Повторно использовать определения и расчёты предыдущих этапов; конкретный объём указан в заданиях ниже.', 'Reuse definitions/calculations from earlier stages; the precise scope is in the tasks below.')

    changes = {
        ('D2',1): ('Своя двухзвенная модель: энергия, состояние и библиотечный эталон', 'Own two-link model: energy, state and library reference',
                  'Для одной плоской 2R-цепи самостоятельно получены T и U, уравнения и M/C/g; заданы состояние, равновесие и локальная линеаризация. Энергия, знаки и единицы проверены; готовая библиотека служит независимым эталоном. Квазистатика сопоставлена с движением при ускорении.',
                  'Independently derive T/U, equations and M/C/g for one planar 2R chain; define state, equilibrium and local linearization. Check energy, signs and units against an independent library; compare quasistatics with accelerated motion.'),
        ('M11',1): ('Fusion без магнитометра: оценка крена и тангажа', 'No-magnetometer Fusion: roll and pitch estimation',
                   'Один выбранный Fusion AHRS обрабатывает калиброванные IMU-данные; проверенная версия записана. Явный адаптер преобразует SI в град/с и g на входе библиотеки. Объяснены quaternion, интегрирование, коррекция наклона, gain, смещение и ограничения при ускорении; абсолютный курс не заявляется наблюдаемым.',
                   'One selected Fusion AHRS processes calibrated IMU data with the tested version recorded. An explicit adapter converts SI to degrees/s and g at the library boundary. Explain quaternion, integration, tilt correction, gain, bias and acceleration limits; do not claim observable absolute heading.'),
        ('M14',0): ('Камера: калибровка, поза и пересечение луча с плоскостью', 'Camera: calibration, pose and ray–plane intersection',
                   'Камера закреплена; intrinsics/дисторсия определены, solvePnP по известной мишени задаёт позу относительно основания. Нормализованный луч пересекается с известной плоскостью высоты целевой точки. Ошибка проверена на независимых физических точках в миллиметрах; неизвестная высота и почти параллельный луч отклоняются.',
                   'Fix the camera; calibrate intrinsics/distortion and obtain its base-relative pose with solvePnP and a known target. Intersect a normalized ray with the known target-height plane. Validate independent physical points in millimetres; reject unknown height and nearly parallel rays.'),
    }
    for (stage,index), (tr,te,rr,re) in changes.items():
        task = estimate['items'][stage]['tasks'][index]
        task['title'], task['result'] = bi(tr,te), bi(rr,re)

    clarifications = {
        ('M10',0): bi('По модели D2 объяснены состояние, полюса и границы локального вывода устойчивости.', 'Explain state, poles and the limits of local stability conclusions using the D2 model.'),
        ('M11',3): bi('Самостоятельно выполнен один скалярный шаг прогноза/коррекции KF с объяснением ковариации и невязки; это не второй AHRS.', 'Independently perform one scalar KF predict/update and explain covariance/innovation; this is not a second AHRS.'),
        ('M16',1): bi('Объяснены конфигурационное пространство и принцип одного выбранного RRT/PRM, включая пример отказа пути.', 'Explain C-space and the principle of one chosen RRT/PRM, including a path-failure example.'),
        ('M16',2): bi('Путь отличён от траектории; один профиль временного масштабирования проверен ручным расчётом.', 'Distinguish path from trajectory and check one time-scaling profile by hand.'),
        ('T2',2): bi('Сохранены раздельные кривые тяги/отпускания, нагрузка и предыстория; простая модель проверена независимой серией по протоколу learning-guides.md.', 'Retain separate pull/release curves, loading and history; validate a simple model with a held-out run using the learning-guides.md protocol.'),
    }
    for (stage,index), extra in clarifications.items():
        result = estimate['items'][stage]['tasks'][index]['result']
        for language,text in extra.items():
            result[language] = result[language].replace(text,'').strip()+' '+text

    for stage in estimate['order']:
        item = estimate['items'][stage]
        if stage not in literature['routes']:
            continue
        route = literature['routes'][stage]
        units = []
        for index, task in enumerate(item['tasks'], 1):
            if not task['learn']:
                continue
            key = f'{stage}.{index}'
            selected = focus.get(key)
            sources = selected[0].split(',') if selected else [r['ref'] for r in route['readings']]
            assert all(ref in refs for ref in sources), key
            assert set(sources) <= {r['ref'] for r in route['readings']}, key
            units.append({'task':key, 'hours':task['learn'], 'sources':sources,
                          'focus':bi(selected[1],selected[2]) if selected else task['title'],
                          'mastery_check': task.get('result') or task['title']})
        assert sum(u['hours'] for u in units) == item['learn'], stage
        route['study_units'] = units
        route['learn_hours'] = item['learn']
        route['study_policy'] = bi('Часы блоков ниже уже входят в изучение этапа. Чтение, разбор и самостоятельное объяснение делят эти часы; реализация и испытания выполняются в существующих заданиях. Полные книги не добавляются.',
                                   'The units below already occupy stage learning hours, shared by reading, worked examples and independent explanation. Implementation/trials remain in existing tasks; no complete books are added.')
        item['core_reading'] = bi('Сначала источники и блоки «Что читать сейчас» с привязкой к заданиям. Все часы изучения распределены там; повторное чтение и полные книги отдельно не прибавляются.',
                                 'Follow the task-linked sources and units in What to read now. All learning hours are allocated there; do not add repeated reading or full books.')

    steps = [
        ('geometry',['M02','M08'],['math-modern-robotics'],'Геометрия → кинематика → статика','Geometry → kinematics → statics','Самостоятельно пересчитать FK/IK/J после изменения длины звена; объяснить сингулярность.','Recompute FK/IK/J after changing a link length and explain singularity.'),
        ('design',['M05','D1','L1','A1'],['H-ROY','H-SLOCUM'],'Нагрузки → конструкция → измерение','Loads → design → measurement','Момент и прогиб из массы/вылета сопоставлены с нагрузочным опытом.','Compare moment/sag from mass/reach with a load test.'),
        ('dynamics',['M07','D2'],['math-modern-robotics','math-contact','math-feedback'],'Модель → энергия → состояние','Model → energy → state','Своя 2R-модель, равновесие и линеаризация; объяснить M/C/g.','Own 2R model, equilibrium and linearization; explain M/C/g.'),
        ('estimation',['M03','M11'],['SW13','math-feedback','math-labbe'],'Измерение → неопределённость → оценивание','Measurement → uncertainty → estimation','Калибровка и независимая ошибка; объяснить дрейф/наблюдаемость и один шаг KF.','Calibration/held-out error; explain drift/observability and one KF step.'),
        ('control',['M10'],['math-feedback'],'Обратная связь → устойчивость → робастность','Feedback → stability → robustness','Объяснить полюса, задержку, насыщение и условия вывода для интервалов параметров.','Explain poles, delay, saturation and inference conditions for parameter intervals.'),
        ('contact',['M13','M19'],['math-contact','math-qp','H-GAIT'],'Контакт → допустимые реакции → походка','Contact → feasible forces → gait','Сила/импульс, плоская QP и отказ LIFT до потери допустимой опоры.','Force/impulse, planar QP and rejecting LIFT before support becomes infeasible.'),
        ('planning',['M16','M17'],['math-modern-robotics','SW07','SW04'],'Путь → траектория → исполнение','Path → trajectory → execution','Объяснить один планировщик, временной профиль и отказ при коллизии/пределе.','Explain one planner, time profile and collision/limit rejection.'),
        ('perception',['M14','M18'],['SW05','SW14','SW09','SW10'],'Пиксель → метрическая цель → проверяемое решение','Pixel → metric target → validated decision','Получить миллиметры в основании и независимую ошибку; исключить утечку данных ML.','Obtain base-frame millimetres/held-out error and exclude ML leakage.'),
        ('tendons',['T1','T2','T3'],['H-OCR','H-SLOCUM','H-TENDON-FRICTION'],'Форма → вес/трение → повторяемое движение','Shape → gravity/friction → repeatable motion','Различить идеальную кинематику и измеренный обратный ход/нагрузку/связь секций.','Distinguish ideal kinematics from measured reversal/loading/section coupling.'),
    ]
    path = {'version':'4.7','updated_on':DATE,'scope':bi('Связная прикладная база обязательных проектов с самостоятельными проверками переноса знаний.', 'Connected applied foundations for the required projects, with independent knowledge-transfer checks.'),
            'hours_policy':bi('701 ч изучения входят в 2 600 ч; линии ниже связывают существующие темы, не добавляя часы. Они пересекаются по времени; фактический порядок работ задаётся календарём.', '701 learning hours are inside 2,600 h; the strands below connect existing topics without adding hours. They overlap in time; follow the calendar for actual work order.'),
            'limits':bi('Полные курсы EKF/LQR, SLAM, динамической ходьбы, MPC/RL и нелинейной континуальной механики остаются отдельным развитием. Прохождение маршрута не объявляется освоением всей робототехники.', 'Full EKF/LQR, SLAM, dynamic walking, MPC/RL and nonlinear continuum mechanics remain further development. Completion is not described as mastery of all robotics.'),
            'steps':[{'id':k,'stages':st,'sources':sr,'title':bi(tr,te),'mastery_check':bi(cr,ce)} for k,st,sr,tr,te,cr,ce in steps]}

    notes = {
        'M11': bi('Основной фильтр — Fusion без магнитометра; Kalman — один ручной шаг для понимания, не вторая реализация. Источники, единицы и проверка — рядом с заданием.', 'Use no-magnetometer Fusion; one hand-worked Kalman step explains estimation without a second implementation. Task-linked sources, units and checks are provided.'),
        'M14': bi('OpenCV — обработка; метрический путь закреплён в литературе: калибровка → solvePnP → луч и известная плоскость → основание. Hand–eye для подвижной камеры не добавляется автоматически.', 'OpenCV covers processing; reading fixes the metric path: calibration → solvePnP → ray/known plane → base. Moving-camera hand–eye is not automatically added.'),
        'M10': bi('Курс — вводный PID. Теория состояния/устойчивости и робастный практикум закрываются выбранными разделами FBS и собственной моделью D2.', 'The course introduces PID. Selected FBS sections and the D2 model cover state/stability theory and the robustness lab.'),
        'M13': bi('Курсы дают интеграцию; физика контакта закреплена в Tedrake Multi-Body Dynamics и собственной лабораторной dt/dt2.', 'Courses cover integration; Tedrake Multi-Body Dynamics and the existing dt/dt2 lab cover contact physics.'),
        'M19': bi('Походки — статья OpenSHC и собственные фазовые диаграммы; контакт — Tedrake; плоская QP — Boyd/CVXPY. ROS-курс используется для инструментов.', 'Use OpenSHC/custom phase diagrams for gait, Tedrake for contact and Boyd/CVXPY for planar QP; ROS courses supply tooling.'),
        'T1': bi('Курсы дают элементы машин. Основные источники хвоста: Slocum о тросовой передаче, OpenContinuum о геометрии, статья Liu/Alambeigi о трении и собственная пассивная секция.', 'Courses cover machine elements. Tail sources: Slocum cable transmission, OpenContinuum geometry, Liu/Alambeigi friction and the custom passive section.'),
        'T2': bi('Преднатяг, обратный ход, нагрузка и связь секций изучаются по литературе и протоколу хвоста; IoT-курс не считается источником этой механики.', 'Study pretension, reversal, loading and segment coupling through reading and the tail protocol; the IoT course does not cover this mechanics.'),
    }
    for stage,note in notes.items():
        courses['core_routes'][stage]['note'] = note
    courses['learning_path'] = 'learning-path.json'
    courses['materials_updated_on'] = DATE
    literature.update(version='4.7', learning_hours_total=701, added_hours=0,
                      learning_path='learning-path.json', routes_updated_on=DATE)
    for stage,route in literature['routes'].items():
        for reading_entry in route['readings']:
            ref = refs[reading_entry['ref']]
            if stage not in ref['stages']:
                ref['stages'].append(stage)
    estimate['version'] = '4.7'
    estimate['materials_revision'] = {'updated_on':DATE,'learning_path':'learning-path.json','notes':'learning-guides.md',
                                    'hours_changed':False,'closed_gaps':['imu','metric-vision','robustness','contact','qp','multilegged-gaits','tendon-friction','connected-foundations']}
    for stage, original in before_hours.items():
        assert original == [(t['learn'],t['build'],t['verify']) for t in estimate['items'][stage]['tasks']]
    # Keep the task-hour report in sync with renamed tasks; reviewed effort stays.
    report = json.loads((ROOT / 'task-hour-review.json').read_text())
    for row in report['tasks']:
        stage, index = row['key'].rsplit('.',1)
        row['title'] = estimate['items'][stage]['tasks'][int(index)-1]['title']
    report['materials_revision'] = '4.7'
    for filename,data in [('estimate.json',estimate),('literature.json',literature),('courses.json',courses),
                          ('learning-path.json',path),('task-hour-review.json',report)]:
        (ROOT / filename).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(f'Bound {sum(len(r["study_units"]) for r in literature["routes"].values())} study units to 701 existing learning hours; 8 gaps addressed.')


if __name__ == '__main__':
    main()
