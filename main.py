import enc_change_id as ecid
import encoders as enc
import step_motor as sm
import dc_motor as dcm


class Menu:

    def __init__(self):
        self.enc_monitor = enc.MultiEncoderMonitor(channel='can0',
                                                   node_ids=[3, 4])

    def show_encoder_data(self):
        self.enc_monitor.start_monitoring()

    def change_encoder_id(self):
        current_id = int(input("Введите текущий Node ID энкодера: "))
        new_id = int(input("Введите новый Node ID энкодера (1-127): "))
        if 1 <= new_id <= 127:
            ecid.change_node_id(current_id, new_id)
        else:
            print("Новый Node ID должен быть в диапазоне 1-127")

    def reset_encoder_position(self):
        node_id = int(
            input("Введите Node ID энкодера для обнуления позиции: "))
        if 1 <= node_id <= 127:
            ecid.reset_encoder_position(node_id)
        else:
            print("Новый Node ID должен быть в диапазоне 1-127")

    def move_step_motor(self):
        with sm.MoveStepMotor(channel='can0', node_id=0x101) as monitor:
            power = int(input("Введите состояние питания (0/1): "))
            direction = int(input("Введите направление вращения (0/1): "))
            steps = int(input("Введите количество шагов: "))
            if monitor.send_motor_command(power, direction, steps):
                print("Команда отправлена и ответ получено успешно")
            else:
                print("Команда отправлена, но ответ не получен")

    def move_dc_motor(self):
        motor_id = int(input("Введите ID мотора (2XX/3XX): "))
        power_state = int(input("Введите состояние питания (0/1): "))
        direction = int(input("Введите направление вращения (0/1): "))
        dcm.send_motor_command('can0', motor_id, power_state, direction)

    def display_menu(self):
        while True:
            print("\nМеню")
            print("1. Показать данные с энкодера")
            print("2. Сменить id энкодера")
            print("3. Обнулить позицию энкодера (по id)")
            print("4. Управлять шаговым двигателем")
            print("5. Управлять двигателем постоянного тока")
            print("0. Выход")

            choice = input("Выберите действие: ")

            if choice == '1':
                self.show_encoder_data()
            elif choice == '2':
                self.change_encoder_id()
            elif choice == '3':
                self.reset_encoder_position()
            elif choice == '4':
                self.move_step_motor()
            elif choice == '5':
                self.move_dc_motor()
            elif choice == '0':
                print("Выход из программы...")
                break
            else:
                print("Неверный выбор. Попробуйте снова.")


if __name__ == "__main__":
    menu = Menu()
    menu.display_menu()
