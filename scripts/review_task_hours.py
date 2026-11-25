"""Apply the individually reviewed nominal hours; never scale learning to fit a date.

Run before render_timeline.py. Each row is learn/build/verify, with its own reason.
The pre-compression comparison is stored in task-hour-review.json on first use.
"""
import copy
import json
import re
from fractions import Fraction
from pathlib import Path
from calendar_settings import VERSION, START, DEADLINE, capacity_minutes, as_hours

ROOT = Path(__file__).resolve().parents[1]
REVIEWED_ON = '2026-11-11'

# New robotics learning is retained or increased. Savings are in familiar coding,
# reused infrastructure and reviews of evidence already produced by experiments.
REVIEW = {
    'M01': [
        ('1/2/1', 'Готовые команды установки и smoke-тесты; знакомые Linux/Git и среда. В 2027 году подготовка и сверка сокращены на 2 ч, новый C++ не затронут.', 'Ready-made installation commands and smoke tests use a familiar Linux/Git environment. The 2027 revision cuts setup and checking by two hours and preserves time for new C++ material.'),
        ('6/4/2', 'Шесть часов нового C++ сохранены; один небольшой компонент вместо учебного приложения.', 'Six hours for new C++ material are preserved. The exercise uses one small component in place of a standalone tutorial app.'),
        ('1/0:30/0:30', 'Python/графики знакомы: готовый скрипт и один контроль. Час изучения единиц и контракта сохранён; снят 1 ч знакомой реализации/сверки.', 'Python and plotting are familiar. Use an existing script and one check. One hour for units and the data contract is preserved, and familiar implementation and checking take one hour less.'),
        ('1/0:30/0:30', 'Знакомое воспроизведение записей на готовом формате; снят 1 ч реализации/сверки. Изучение и физические очередь/watchdog M06 сохранены.', 'Replay uses a familiar workflow and an existing format, cutting one hour of implementation and checking. Learning and the physical queue and watchdog work in M06 are preserved.'),
    ],
    'S1': [
        ('6/4/2', 'ROS новый: понятия графа, сообщений и времени изучаются на одном имитаторе.', 'ROS is new. Learn graphs, messages and timing with one simulator.'),
        ('2/2/1', 'Один launch и конфигурация; повторная инфраструктура проекта не создаётся.', 'Use one launch file and configuration and reuse the project infrastructure.'),
        ('6/7/6', 'Отдельное время на QoS, запись/воспроизведение и отрицательный сценарий.', 'Allow separate time for QoS, recording and replay, and a failure case.'),
    ],
    'M02': [
        ('2/2/1', 'Высшая математика изучалась ранее: диагностика и адресное восстановление.', 'Use a diagnostic and targeted review of previously studied university mathematics.'),
        ('5/4/1', 'Ручной геометрический пример обязателен; NumPy и визуализация уже знакомы.', 'A hand-worked geometry example is required. NumPy and visualisation are familiar.'),
        ('6/5/2', 'Обусловленность и независимая проверка изучаются полностью; используется готовый QR/SVD.', 'Cover conditioning and independent validation in full using existing QR/SVD routines.'),
        ('5/4/1', 'Производная восстанавливается на одном звене, код конечных разностей короткий.', 'Review derivatives on one link with a short finite-difference implementation.'),
        ('5/4/2', 'Один ОДУ-пример и два шага; готовый решатель вместо собственной численной библиотеки.', 'Use one ODE example and two step sizes with an existing solver.'),
        ('0/3/4', 'Единый проверяемый модуль; время оставлено на объяснение ошибок единиц и вырожденности.', 'Build one testable module and retain time to explain unit errors and degeneracy.'),
    ],
    'M04': [
        ('26/9/5', 'Электроника с нуля: токовые пути, схема, расчёт, паспорт и самостоятельное измерение.', 'Electronics starts from scratch and covers current paths, schematics, calculations, datasheets and independent measurements.'),
        ('10/13/5', 'Новые ручные навыки пайки/обжима и подключения приборов требуют практики.', 'Practise the new manual skills of soldering, crimping and connecting instruments.'),
        ('8/13/5', 'RC, логические уровни и защита нагрузки изучаются с физическими опытами.', 'Learn RC circuits, logic levels and load protection through physical experiments.'),
        ('12/10/4', 'Сигналы новые; Python используется как инструмент без повторного обучения языку.', 'Signals are new. Use familiar Python as a tool.'),
    ],
    'M05': [
        ('16/15/3', 'Новый CAD: ограничения эскиза, параметризация и самостоятельное воспроизведение.', 'CAD is new. Cover sketch constraints, parametrisation and independent reproduction.'),
        ('13/25/5', 'Первая собственная трёхосная сборка, кабельные трассы и доступ к крепежу.', 'Build the first custom three-axis assembly, including cable routing and fastener access.'),
        ('13/14/6', 'Посадки и элементы конструкций новые; образцы и повторная сборка обязательны.', 'Fits and structural features are new. Test samples and repeat the assembly.'),
        ('20/9/4', 'Механика новая: ручная статика, прочность, прогиб и ограничения материала.', 'Mechanics is new. Work out statics, strength, deflection and material limits by hand.'),
        ('2/8/7', 'Профиль имеющегося принтера используется повторно; измерения образцов сохранены.', 'Reuse the existing printer profile and retain sample measurements.'),
    ],
    'M06': [
        ('9/8/2', 'Новые MCU и электрические пределы; обычная организация кода уже знакома.', 'Microcontrollers and electrical limits are new. Code organisation is familiar.'),
        ('12/13/5', 'Освоение периферии и одной реальной шины по измеренным сигналам.', 'Learn peripherals and one physical bus using measured signals.'),
        ('3/10/4', 'Формат пакета и владение данными используют опыт разработки; ограничения MCU изучаются отдельно.', 'Apply prior development experience to packet format and data ownership. Study MCU constraints separately.'),
        ('9/10/6', 'Новые RTOS/ISR, измерение джиттера и аппаратный watchdog.', 'RTOS and ISRs are new, along with jitter measurement and the hardware watchdog.'),
        ('5/14/10', 'Физические F1–F10 и независимая остановка сохранены полностью.', 'Preserve all physical F1–F10 tests and the independent stop.'),
    ],
    'M07': [
        ('12/10/4', 'Новые приводы/редукторы: требования, передаточное отношение, потери и люфт.', 'Actuators and gearboxes are new. Cover requirements, gear ratio, losses and backlash.'),
        ('10/13/8', 'Новый физический стенд, калибровки и нагрев; измерения не заменяются симуляцией.', 'Build a new physical rig and measure calibration and heating on the hardware.'),
        ('8/12/5', 'Первый позиционный контур на готовом стенде; границы и остановка обязательны.', 'Implement the first position loop on the existing rig, including limits and stop behaviour.'),
        ('4/7/11', 'Идентификация, независимый нагрузочный опыт и повтор после охлаждения.', 'Include identification, an independent load test and a repeat after cooling.'),
    ],
    'M08': [
        ('6/8/2', 'Новые робототехнические системы координат; общая математика и CAD уже подготовлены.', 'Robot coordinate frames are new. General mathematics and CAD are already in place.'),
        ('5/10/3', 'FK собственной ноги, эталонные позы и зеркальность; один общий модуль.', 'Use one shared module for custom leg FK, reference poses and mirroring.'),
        ('7/10/4', 'Ветви IK, достижимость и вся траектория, а не только учебная конечная точка.', 'Check IK branches, reachability and the full trajectory, including intermediate poses.'),
        ('7/8/4', 'Якобиан и виртуальная работа изучаются полностью; код и тестовые данные переиспользуются.', 'Cover the Jacobian and virtual work in full. Reuse code and test data.'),
        ('5/6/2', 'Один готовый численный метод IK на короткой цепи; собственный оптимизатор не нужен.', 'Use one existing numerical IK method on a short chain.'),
        ('3/5/4', 'Опорная точка и контракт используют уже реализованные преобразования.', 'Use the existing transforms for the support point and interface contract.'),
    ],
    'D1': [
        ('7/10/4', 'Новая оценка реальной массы/инерции и нагрузок до выбора окончательной комплектации.', 'Estimate actual mass, inertia and loads before selecting the final configuration.'),
        ('7/9/5', 'Опоры, сцепление и устойчивость: самостоятельный расчёт и контрпример.', 'Work out support, traction and stability independently and include a counterexample.'),
    ],
    'L1': [
        ('3/4/4', 'Паспорт и измерение именно интеллектуального сервопривода, отдельно от DC-стенда.', 'Read the smart servo datasheet and measure the servo itself separately from the DC rig.'),
        ('2/10/2', 'Готовая параметрическая нога адаптируется к фактическим креплениям.', 'Adapt the existing parametric leg to the actual mounts.'),
        ('2/8/3', 'Одна физическая трёхосная сборка с уже освоенными проводкой и остановкой.', 'Assemble one physical three-axis leg using the wiring and stop methods already practised.'),
        ('2/8/5', 'Новый конкретный драйвер и цикл шины; общий протокол и анализ уже готовы.', 'Learn the specific new driver and bus cycle. Reuse the shared protocol and analysis.'),
        ('3/7/13', 'Внешняя проверка FK/IK, нагрузка, нагрев и охлаждение сохранены.', 'Retain external FK/IK validation, load, heating and cooling checks.'),
    ],
    'G1': [('0/1/3', 'Решение по готовым данным L1 и один контроль, без повторения всей серии.', 'Make the decision from the L1 data and one confirmation check.')],
    'M03': [
        ('5/4/2', 'Новая измерительная статистика на уже собранном IMU-журнале.', 'Learn measurement statistics using the existing IMU log.'),
        ('5/7/3', 'Одна реальная калибровка; транспорт, сбор и графики используются готовые.', 'Perform one physical calibration using existing transport, collection and plotting.'),
        ('4/4/3', 'Один метод неопределённости с независимой ошибкой; пакет анализа переиспользуется.', 'Apply one uncertainty method with an independent error check. Reuse the analysis package.'),
        ('4/5/2', 'Один готовый SciPy-решатель; ограничения и утечки данных изучаются отдельно.', 'Use one existing SciPy solver and study constraints and data leakage separately.'),
    ],
    'S2': [
        ('6/7/4', 'URDF/TF и преобразования во времени новые; запас изучения увеличен.', 'URDF, TF and time-dependent transforms are new, so the learning allowance is larger.'),
        ('7/11/5', 'Собственный адаптер ros2_control на C++ получает 23 ч вместо 13.', 'Allow 23 hours, up from 13, for a custom ros2_control adapter in C++.'),
        ('5/4/5', 'Новые исполнитель и жизненный цикл; готовые сценарии отказов используются повторно.', 'Executors and lifecycle behaviour are new. Reuse the existing failure cases.'),
    ],
    'D2': [
        ('7/8/3', 'Вывод одной физической модели; интегратор и измерительный стенд уже готовы.', 'Derive one physical model using the existing integrator and measurement rig.'),
        ('6/5/2', 'Самостоятельный вывод одной плоской 2R-модели и независимый библиотечный эталон; полный вывод 6-DOF не добавляется.', 'Derive one planar 2R model and obtain an independent library reference. The scope covers the planar model.'),
        ('6/11/6', 'Реальная независимая серия и объяснение расхождений сохранены.', 'Preserve an independent physical test series and explain discrepancies.'),
    ],
    'M11': [
        ('4/4/2', 'Оси/единицы изучаются, но калибровка M03 и формат M06 не создаются заново.', 'Study axes and units and reuse M03 calibration and the M06 data format.'),
        ('8/10/4', 'Новый AHRS/комплементарный фильтр и физический смысл его параметров.', 'Learn the AHRS/complementary filter and the physical meaning of its parameters.'),
        ('7/8/4', 'Физические эталоны, дрейф и отказ; дополнительное время на интерпретацию.', 'Allow time for physical references, drift, a failure case and interpretation.'),
        ('2/3/4', 'Наблюдаемость изучается явно; общий контракт качества данных уже есть.', 'Study observability explicitly and reuse the shared data quality contract.'),
    ],
    'M10': [
        ('7/8/3', 'Теория PID сохранена; используются модель D2 и стенд M07.', 'Retain PID theory and use the D2 model and M07 rig.'),
        ('5/7/3', 'Дискретизация и задержки изучаются; измерительный код берётся из M06.', 'Study discretisation and delays using the M06 measurement code.'),
        ('4/9/4', 'Физическая настройка и независимые подтверждающие повторы.', 'Tune on hardware and run independent confirmation trials.'),
        ('6/8/4', 'Новый внешний контур использует готовые IMU и IK.', 'The new outer loop uses the existing IMU and IK.'),
        ('0/2/4', 'Общий анализ и регрессионные журналы используются повторно.', 'Reuse the shared analysis and regression logs.'),
        ('6/7/7', 'Вводная robust-лабораторная: одна линейная ось, полюса/запасы и контрпример; не полный robust-курс.', 'The introductory robust control lab covers one linear axis, poles, margins and a counterexample.'),
    ],
    'M13': [
        ('6/7/5', 'Симуляция новой физики на готовых URDF, геометрии и установленном движке.', 'Simulate new physics using the existing URDF, geometry and installed engine.'),
        ('5/5/4', 'Контакт и модельные сенсоры изучаются отдельно от интерфейсного кода.', 'Study contact and simulated sensors separately from interface code.'),
        ('8/8/6', 'HIL и согласование времени новые; выделено 22 ч на одну замкнутую связку.', 'HIL and synchronisation are new. Allow 22 hours for one closed-loop setup.'),
        ('4/5/5', 'Готовый физический сценарий L1 сопоставляется с моделью, без второй серии разработки.', 'Compare the existing physical L1 case with the model.'),
        ('4/7/5', 'Вводный контактный опыт на существующей стопе и движке; эталоны и dt/dt2 сохранены.', 'Run an introductory contact experiment with the existing foot and engine. Preserve the references and the dt and dt/2 checks.'),
    ],
    'A1': [
        ('15/16/6', 'Новая шестикоординатная конструкция, плечевые нагрузки и выбор приводов.', 'The six-axis design, arm loads and actuator selection are new.'),
        ('8/26/14', 'Нагруженный физический прототип до заказа остальных приводов.', 'Test a loaded physical prototype before ordering the remaining actuators.'),
        ('13/48/10', 'Собственная CAD-механика, модель и готовый IK получают 71 ч; суммы подработ согласованы.', 'Allow 71 hours for custom mechanical CAD, the model and an existing IK implementation. The subtasks add up to that total.'),
        ('4/15/5', 'Простой параллельный захват; CAD и стендовая методика уже освоены.', 'Use a simple parallel gripper and established CAD and bench methods.'),
    ],
    'T1': [
        ('14/14/6', 'Континуальная геометрия и нагрузка новые: теория не сокращается из-за Python-опыта.', 'Continuum geometry and loading are new and receive the full theory allowance.'),
        ('13/31/12', 'Три варианта хребта и пассивная секция: изготовление и сравнение физических образцов.', 'Build and compare physical samples for three backbone variants and one passive section.'),
        ('10/29/11', 'Новые тросовые передачи, натяжение, трение и гистерезис.', 'Learn cable transmissions, tensioning, friction and hysteresis.'),
    ],
    'M19': [
        ('4/6/3', 'Параметрическое тиражирование готовой ноги, без повторного моделирования каждого сустава.', 'Replicate the existing parametrised leg design across joints.'),
        ('6/10/4', 'Новая логика контактов поверх готовых фильтра и временных меток.', 'Add new contact logic on top of the existing filter and timestamps.'),
        ('7/13/4', 'Новая походка и перенос веса; программный автомат использует обычный опыт разработки.', 'Gait and weight transfer are new. The software state machine uses familiar techniques.'),
        ('6/9/4', 'Новый выбор опоры использует готовые IK и проверки всей дуги.', 'New foothold selection uses existing IK and checks the full swing arc.'),
        ('7/12/4', 'Физически осмысленное свободное стояние и возмущение сохраняются.', 'Retain physically meaningful unsupported standing and disturbance tests.'),
        ('4/8/5', 'Один параметризованный набор регрессий использует существующие механизмы отказов.', 'A single parameterised regression suite uses the existing failure mechanisms.'),
        ('7/8/5', 'Одна плоская QP с готовым решателем и ручным эталоном; не полноценное силовое управление.', 'Solve one planar QP with an existing solver and a hand-worked reference. The exercise covers force allocation.'),
    ],
    'M22': [
        ('6/8/4', 'Новые нагрузки четырёх ног; шаблоны массы/питания уже готовы.', 'Four-leg loads are new. The mass and power templates already exist.'),
        ('5/32/8', 'Физическое изготовление ещё трёх ног и корпуса сохранено.', 'Retain physical fabrication of three additional legs and the body.'),
        ('4/17/8', 'Новая многоприводная разводка, последовательный запуск и независимая остановка.', 'Multi-actuator wiring, sequential startup and independent stopping are new.'),
        ('4/13/10', 'Все 12 физических калибровок сохранены; общий скрипт и протокол используются повторно.', 'Retain all 12 physical calibrations and reuse the shared script and protocol.'),
        ('1/8/17', 'Стояние, crawl и заранее заданная серия попыток сохраняются; анализ единым скриптом.', 'Retain standing, crawl and the predefined trials. Use one analysis script.'),
    ],
    'G2': [('0/1/3', 'Приёмка уже выполненной серии M22, без второго полного испытания.', 'Base acceptance on the completed M22 trials.')],
    'T2': [
        ('8/27/12', 'Первая активная секция: новое управление тросовой механикой и её физические ограничения.', 'The first active section introduces cable mechanism control and its physical limits.'),
        ('7/38/12', 'Три секции/шесть приводов; монтаж и проверка дальних тросов сохранены.', 'Preserve installation and checks of the remote cable runs across three sections and six actuators.'),
        ('7/22/17', 'Новая калибровка формы и взаимовлияния; независимые измерения сохранены.', 'Shape and coupling calibration are new. Preserve independent measurements.'),
    ],
    'M23': [
        ('5/22/5', 'Добавление двух ног по уже принятой технологии, с повторным расчётом корпуса.', 'Add two legs using the accepted fabrication method and recalculate the body.'),
        ('2/8/7', 'Все 18 каналов проверяются; инструменты калибровки и анализа переиспользуются.', 'Check all 18 channels and reuse calibration and analysis tools.'),
        ('7/15/7', 'Новые wave/ripple изучаются полностью на готовом автомате crawl.', 'Cover the new wave and ripple gaits in full using the existing crawl state machine.'),
        ('8/12/10', 'Новые плоскость опоры и уклоны; датчики и контур ориентации уже готовы.', 'The support plane and slopes are new. The sensors and orientation loop are ready.'),
        ('3/9/20', '40 физических попыток и тепловые/энергетические данные сохранены; один итоговый пакет.', 'Preserve 40 physical trials plus thermal and power data in one final evidence package.'),
    ],
    'M16': [
        ('3/4/3', 'Новый MoveIt подключается к готовой модели A1; URDF повторно не создаётся.', 'Integrate MoveIt with the existing A1 model and reuse its URDF.'),
        ('3/4/3', 'Одна сцена и готовый планировщик, с самостоятельной проверкой отказов.', 'Use one scene and an existing planner with independent failure checks.'),
        ('3/4/3', 'Временная параметризация и проверка реальных пределов всей траектории.', 'Cover time parametrisation and check physical limits along the entire trajectory.'),
        ('3/4/3', 'Готовые ROS-контракты S2 используются для отмены и устаревшей сцены.', 'Reuse S2 ROS contracts for cancellation and stale scene handling.'),
    ],
    'A2': [
        ('3/37/9', 'Полная собственная физическая сборка; изготовление и контроль диапазонов сохранены.', 'Retain full custom physical assembly, fabrication and range-of-motion checks.'),
        ('3/22/9', 'Питание/жгуты и поддержка вертикальных звеньев сохраняются; методика остановки уже освоена.', 'Retain power wiring, harnesses and support for vertical links. The stop method is already established.'),
        ('8/21/18', 'Новые калибровки осей/TCP, люфт и прогиб; повторно используется анализ M03.', 'Axis and TCP calibration, backlash and deflection are new. Reuse M03 analysis.'),
    ],
    'M17': [
        ('2/3/2', 'Один обычный автомат состояний; поведение хватания новое, программная техника знакома.', 'Use a conventional state machine. Grasping behaviour is new and the programming technique is familiar.'),
        ('2/2/2', 'Согласовать уже существующие интерфейсы, не реализовывать второй ROS-слой.', 'Align existing interfaces within the shared ROS layer.'),
        ('1/1/1', 'Минимальное разрешение/отмена в существующем интерфейсе, без отдельного UI-проекта.', 'Add minimal authorisation and cancellation controls to the existing interface.'),
    ],
    'M14': [
        ('8/8/5', 'Новая геометрическая калибровка камеры и независимые позы сохраняются.', 'Retain the new geometric camera calibration and independent test poses.'),
        ('3/5/3', 'Один простой цветовой/геометрический метод в фиксированной рабочей области.', 'Use one simple colour or geometry method in a fixed workspace.'),
        ('3/4/3', 'Новая связь камера–манипулятор; готовые преобразования и границы используются повторно.', 'The camera-to-arm relationship is new. Reuse the existing transforms and limits.'),
        ('2/3/3', 'Один ROS-узел на готовом каркасе S2, со всеми отрицательными сценариями.', 'Build one ROS node on the S2 scaffold and retain all failure cases.'),
    ],
    'M18': [
        ('6/7/5', 'Новые разбиения по сеансам; сбор и ROI используются из M14.', 'Session-based splits are new. Reuse data collection and ROI from M14.'),
        ('8/7/3', 'Новый цикл PyTorch и одна небольшая модель; Python/DataLoader-код короткий.', 'The PyTorch training loop and one small model are new. Keep Python and DataLoader code short.'),
        ('6/5/7', 'Новые метрики и выбор порога изучаются; анализ автоматизирован без сокращения тестовых случаев.', 'Learn new metrics and threshold selection. Automate analysis and retain the complete test set.'),
        ('2/4/4', 'Одна CPU-модель в готовом ROS-конвейере; физическая проверка включена в A3.', 'Deploy one CPU model to the existing ROS pipeline. A3 includes the physical check.'),
    ],
    'A3': [
        ('3/19/8', 'Один реальный исполнитель на готовых S2/MoveIt и измеренной модели A2.', 'Use one real executor with the existing S2 and MoveIt setup and the measured A2 model.'),
        ('4/16/12', 'Все 30 переносов, удержание и случай 500 г сохранены; подсчёт и графики автоматические.', 'Retain all 30 transfers, the hold test and the 500 g case. Automate counts and plots.'),
        ('4/17/13', 'Все 100 циклов, осмотры, тепловой опыт и отказы сохранены; отчёт из общих журналов.', 'Retain all 100 cycles, inspections, thermal testing and failure cases. Report from the shared logs.'),
    ],
    'G3': [('0/1/3', 'Сверка физической серии A3 и результата ML; повторять всю серию не требуется.', 'Review the A3 physical trial series and ML results for acceptance.')],
    'T3': [
        ('3/18/6', 'Пять движений и минимальный редактор на готовых ROS/прошивке; без второго UI-фреймворка.', 'Use the existing ROS and firmware setup for five motions and a minimal editor.'),
        ('3/11/9', '100 циклов, отказы, манекен и примерка сохранены; шаблоны испытаний и выпуска общие.', 'Retain 100 cycles, failure cases, mannequin and fitting checks. Share test and release templates.'),
    ],
    'M24': [
        ('0/0:30/1:30', 'Сверить готовую матрицу доказательств, собранную по ходу работ; на новую вёрстку и повторный обзор снят 1 ч.', 'Check the evidence matrix assembled throughout the work. Cut one hour of new layout and repeat review.'),
        ('1/1:30/1:30', 'Упаковать существующие CI/окружение/CAD по единому шаблону; снят 1 ч повторной организации. Изучение сохранено.', 'Package existing CI, environment and CAD assets using one template. Cut one hour of reorganisation and retain the learning time.'),
        ('0/0:30/2:30', 'Воспроизвести те же три готовых сценария общим запуском; снят 1 ч подготовки и оформления. Физическая приёмка не повторяется.', 'Reproduce the same three existing scenarios through a shared launch. Cut one hour of setup and presentation and reuse the physical acceptance evidence.'),
        ('1/0:30/1:10', 'Портфолио из готовых материалов по короткому шаблону; сняты 1 ч 20 мин подготовки/редактирования. Час изучения и объяснение решений сохранены.', 'Build the portfolio from existing materials using a short template. Cut one hour and 20 minutes of setup and editing and retain one hour of study and the design explanation.'),
    ],
    'G4': [('0/1/3', 'Итоговое решение по собранным доказательствам всех проектов, без второго выпуска.', 'Make the final decision using the evidence already collected across all projects.')],
}


def parse_effort(value):
    if ':' in value:
        hours,minutes = map(int,value.split(':'))
        return hours*60+minutes
    minutes = Fraction(value)*60
    assert minutes.denominator == 1
    return int(minutes)


def display_hours(value):
    hours,minutes = divmod(round(value*60),60)
    return str(hours) if not minutes else f'{hours}:{minutes:02}'


def main():
    estimate = json.loads((ROOT / 'estimate.json').read_text())
    review_path = ROOT / 'task-hour-review.json'
    prior = json.loads(review_path.read_text()) if review_path.exists() else None
    # Archived estimate is used only on initial review, never by the renderer.
    if prior is None:
        import subprocess
        baseline = json.loads(subprocess.check_output(
            ['git', 'show', '156da32:estimate.json'], cwd=ROOT))
    reviewed = []
    for stage in estimate['order']:
        item = estimate['items'][stage]
        if item['track'] in {'reserve', 'capacity'}:
            continue
        assert stage in REVIEW and len(REVIEW[stage]) == len(item['tasks']), stage
        for index, (task, (values, reason, reason_en)) in enumerate(zip(item['tasks'], REVIEW[stage])):
            key = f'{stage}.{index + 1}'
            minutes = dict(zip(('learn','build','verify'),map(parse_effort,values.split('/'))))
            hours = {key:as_hours(value) for key,value in minutes.items()}
            previous = next((r for r in prior['tasks'] if r['key'] == key), None) if prior else None
            old = previous['before'] if previous else {c: task[c] for c in hours}
            floor = previous['pre_compression_learn'] if previous else baseline['items'][stage]['tasks'][index]['learn']
            assert stage == 'M01' or hours['learn'] >= floor, f'New learning cut: {key}'
            task.update(hours, hours=as_hours(sum(minutes.values())))
            reviewed.append({'key': key, 'stage': stage, 'title': task['title'],
                             'before': old, 'pre_compression_learn': floor,
                             'after': hours, 'hours': task['hours'], 'reason': reason,
                             'reason_en': reason_en})
        item.update({c: sum(t[c] for t in item['tasks']) for c in ('learn', 'build', 'verify')})
        item['base'] = item['hours'] = as_hours(sum(round(t['hours']*60) for t in item['tasks']))
        old_rationale = copy.deepcopy(item.get('rationale'))
        item['rationale'] = {
            'ru': f"{display_hours(item['hours'])} ч: изучение {display_hours(item['learn'])}, реализация {display_hours(item['build'])}, проверка {display_hours(item['verify'])}. "
                  'Индивидуальная средняя рабочая оценка для указанного опыта; новые темы изучаются полностью в границах задания. '
                  'Готовые код, стенды, журналы и методики используются повторно. Обычная отладка входит в реализацию; отдельный процент на непредсказуемые переделки не добавлен.',
            'en': f"{display_hours(item['hours'])} h: learning {display_hours(item['learn'])}, implementation {display_hours(item['build'])}, verification {display_hours(item['verify'])}. "
                  'Individually reviewed nominal effort for the stated experience; new topics retain their defined learning scope. '
                  'Reuse code, rigs, logs and protocols. Implementation includes routine debugging; no blanket rework percentage is added.'}
        item['hour_review'] = {'reviewed_on': REVIEWED_ON, 'report': 'task-hour-review.json'}
        if item.get('core_reading'):
            for language, value in item['core_reading'].items():
                value = re.sub(r'\d+ учебн(?:ый час|ых часов|ых часа)', f"{item['learn']} ч изучения", value)
                value = re.sub(r'\d+ learning hours', f"{item['learn']} learning hours", value)
                item['core_reading'][language] = value
        # Save old prose for exact replacement of rendered copies, not global numbers.
        if not prior:
            for row in reviewed[-len(item['tasks']):]:
                row['previous_stage_rationale'] = old_rationale
    estimate['items']['A1']['tasks'][2]['result'] = {
        'ru': 'Собственные звенья, опоры и CAD — 46 ч; URDF/SRDF, столкновения, массы и ограничения — 16 ч; настройка готового численного IK для шести степеней свободы, достижимость и сингулярности — 9 ч. Итого 71 ч; изучение, реализация и проверка входят в эти подработы.',
        'en': 'Custom links/supports/CAD: 46 h; URDF/SRDF, collisions, masses and limits: 16 h; configuring existing numerical six-DOF IK, reachability and singularities: 9 h. Total 71 h, including learning, implementation and verification.'}
    estimate['items']['M01']['tasks'][0]['result'] = {
        'ru': 'Зафиксированы Ubuntu 24.04 ARM64, компилятор, RMW и версии Jazzy/Harmonic; готовые talker/listener, RViz, сцена тележки и сцена датчика имеют результат PASS/HOLD. Четыре часа — применение знакомых Linux/Git и готовых команд установки, без повторного вводного курса; ознакомление с планом 2 января проводится отдельно.',
        'en': 'Record Ubuntu 24.04 ARM64, compiler, RMW and Jazzy/Harmonic versions; supplied talker/listener, RViz, cart and sensor scenes have PASS/HOLD results. Four hours apply existing Linux/Git skills and installation commands; 2 January orientation is separate.'}
    estimate.pop('timeline_compression', None)
    total_minutes = sum(round(row['hours']*60) for row in reviewed)
    total = as_hours(total_minutes)
    capacity = capacity_minutes()
    assert total_minutes <= capacity, f'Nominal estimate exceeds annual capacity: {total_minutes} > {capacity}'
    estimate['version'] = VERSION
    estimate['hour_review'] = {'reviewed_on': REVIEWED_ON, 'tasks_reviewed': len(reviewed),
        'report': 'task-hour-review.json', 'method': 'individual nominal effort, no proportional compression',
        'new_learning_floor_source': '156da32:estimate.json',
        'unpredictable_rework_percentage': 0}
    estimate['source_model'] = 'Individually reviewed nominal task effort for experienced Python/TS developer; new hardware/robotics learning preserved.'
    estimate['reports_scope'] = 'Math/software/hardware reports preserve earlier scope mappings and dependency provenance. Active hours are estimate.items task sums, reviewed in task-hour-review.json.'
    report = {'reviewed_on': REVIEWED_ON, 'version': VERSION,
        'profile': estimate['reports']['math']['profile'],
        'basis': 'Nominal planning judgments, not measured population means or a guarantee of mastery. Routine debugging included; no blanket rework allowance.',
        'pre_compression_reference': '156da32:estimate.json',
        'base_hours': total, 'base_minutes':total_minutes, 'capacity_hours':as_hours(capacity),
        'calendar_adjustment':{'removed_minutes':500,'scope':'M01 familiar environment/Python/replay and M24 release organization; learning and physical trials retained'},
        'category_hours': {c: as_hours(sum(round(r['after'][c]*60) for r in reviewed)) for c in ('learn', 'build', 'verify')},
        'tasks': reviewed}
    if prior:
        for row in reviewed:
            old_row = next(r for r in prior['tasks'] if r['key'] == row['key'])
            row['previous_stage_rationale'] = old_row.get('previous_stage_rationale')
    (ROOT / 'estimate.json').write_text(json.dumps(estimate, ensure_ascii=False, indent=2) + '\n')
    review_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    lines = ['# Индивидуальная проверка часов программы', '',
        f'11.11.2026 · редакция {VERSION} · средняя рабочая оценка для профиля из плана.', '',
        'Профиль: 10 лет Python/TS, основы C++/Rust, ранее изученная высшая математика; механика, CAD и электроника новые.', '',
        f"Проверены все {len(reviewed)} заданий. Всего **{display_hours(total)} ч**: изучение **{display_hours(report['category_hours']['learn'])}**, реализация **{display_hours(report['category_hours']['build'])}**, проверка **{display_hours(report['category_hours']['verify'])}**. Доступно **{display_hours(as_hours(capacity))} ч** с {START:%d.%m.%Y} по {DEADLINE:%d.%m.%Y}. 2 января — ознакомление; учёба с понедельника, 4 января. Время в формате ч:мин.", '',
        'Для сохранения 50 ч/неделю в 2027 году сняты 8 ч 20 мин со знакомой подготовки среды, Python/записей и оформления общего выпуска. Все 701 ч изучения и физические испытания сохранены.', '',
        'Новые темы не сокращаются пропорционально дедлайну: в каждом задании вне M01 часы изучения не ниже редакции до механического сокращения 120 ч. В M01 сокращены знакомые Python/Linux и обработка записей; шесть часов нового C++ сохранены. Часы — инженерная оценка ограниченного прикладного результата, а не измеренная норма полного освоения дисциплины.', '',
        'Обычная отладка входит в реализацию. Отдельный процент на непредсказуемые переделки не добавлен. Число физических опытов, циклов, нагрузок и критерии допуска сохранены. Экономия проверки означает использование общего анализа и уже полученных доказательств, а не пропуск физических испытаний.', '',
        'Чтение и выбранные уроки входят в изучение. Перерывы, автономная печать и доставка не считаются активными часами. 50 ч в неделю — продуктивная работа Пн–Сб. Календарь остаётся условным по наличию деталей; план не предполагает мгновенной доставки.', '',
        '## Все задания', '',
        '| Задание | Тема | Было | Изучение | Реализация | Проверка | Всего | Обоснование |',
        '|---|---|---:|---:|---:|---:|---:|---|']
    for row in reviewed:
        a = row['after']
        lines.append(f"| {row['key']} | {row['title']['ru']} | {display_hours(sum(row['before'].values()))} | {display_hours(a['learn'])} | {display_hours(a['build'])} | {display_hours(a['verify'])} | {display_hours(row['hours'])} | {row['reason']} |")
    (ROOT / 'task-hour-review.md').write_text('\n'.join(lines) + '\n')
    print(f"Reviewed {len(reviewed)} tasks: {display_hours(total)} h; remaining {capacity-total_minutes} minutes.")


if __name__ == '__main__':
    main()
