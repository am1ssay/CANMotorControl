import can
import time


def send_motor_command(channel, motor_id, power_state, direction):
    """
    Отправляет команду управления мотором по CAN-шине.
    
    :param channel: Интерфейс CAN (например, 'can0')
    :param motor_id: ID мотора (например, 201)
    :param power_state: Состояние питания (0 - выкл, 1 - вкл)
    :param direction: Направление вращения (0 - одно, 1 - другое)
    """
    str_id = f"{motor_id:03d}"  # Дополняем до 3 цифр, например 1 → "001"
    if len(str_id) != 3:
        raise ValueError(
            "ID должен быть трехзначным числом (например, 201, 305).")

    group = str_id[0]  # Первая цифра (2 или 3)
    node = str_id[1:]  # Последние две цифры (номер узла)

    if group not in ("2", "3"):
        raise ValueError(
            "ID должен начинаться с 2 или 3 (например, 2XX или 3XX).")

    # Собираем HEX-идентификатор (например, 201 → 0x201)
    motor_id_hex = int(f"0x{group}{node}", 16)

    # Проверяем диапазон (0x200-0x3FF)
    if not (0x200 <= motor_id_hex <= 0x3FF):
        raise ValueError(
            "Некорректный ID мотора. Допустимые диапазоны: 2XX и 3XX.")

    # Формируем данные сообщения
    data = [
        power_state,  # первый байт: состояние (0x00 или 0x01)
        direction  # второй байт: направление (0x00 или 0x01)
    ]

    # Создаем CAN сообщение
    message = can.Message(arbitration_id=motor_id_hex,
                          data=data,
                          is_extended_id=False)

    try:
        # Создаем шину и отправляем сообщение
        with can.Bus(channel=channel, interface='socketcan') as bus:
            bus.send(message)
            print(
                f"Отправлено сообщение: ID={hex(motor_id_hex)}, Данные={data}")
    except can.CanError as e:
        print(f"Ошибка отправки сообщения: {e}")
    finally:
        if bus is not None and bus.state != can.BusState.ERROR:
            bus.shutdown()


# Пример использования
if __name__ == "__main__":
    try:
        motor_id = int(input("Введите ID мотора (2XX/3XX): "))
        power = int(input("Состояние (0/1): "))
        direction = int(input("Направление (0/1): "))
        send_motor_command('can0', motor_id, power, direction)
        time.sleep(2)
        send_motor_command('can0', motor_id, 0, 0)
    except ValueError as e:
        print(f"Ошибка: {e}")
