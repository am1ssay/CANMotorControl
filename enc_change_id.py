import canopen
import argparse
import time


def change_node_id(current_node_id,
                   new_node_id,
                   channel='can0',
                   bitrate=500000):
    network = canopen.Network()
    network.connect(channel=channel, bustype='socketcan', bitrate=bitrate)

    try:
        # Добавляем узел с текущим Node ID
        node = network.add_node(current_node_id, 'eds.eds')

        # Включаем heartbeat (1000 мс)
        node.sdo['Producer Heartbeat Time'].raw = 1000

        # Записываем новый Node ID (объект 0x3001)
        node.sdo['Node ID'].raw = new_node_id
        print(f"==> Запись Node ID: {new_node_id}")

        # Сохраняем параметры в EEPROM
        node.sdo['Store parameters']['Save All Parameters'].raw = 0x65766173
        time.sleep(0.5)  # Задержка для сохранения

        # Переводим узел в OPERATIONAL перед перезагрузкой
        node.nmt.state = 'OPERATIONAL'
        time.sleep(0.2)

        # Перезагружаем узел
        node.nmt.state = 'RESET'
        time.sleep(2)  # Задержка на перезагрузку

        # Подключаемся к новому Node ID
        network.disconnect()
        network.connect(channel=channel, bustype='socketcan', bitrate=bitrate)
        new_node = network.add_node(new_node_id, 'eds.eds')

        # Активируем PDO
        new_node.nmt.state = 'OPERATIONAL'  # Включаем передачу данных [[4]]
        new_node.tpdo.read()  # Загружаем конфигурацию TPDO
        new_node.rpdo.read()  # Загружаем конфигурацию RPDO

        # Включаем автоматическую отправку PDO
        for pdo in new_node.tpdo.values():
            pdo.enabled = True
            pdo.save()

        print(f"✓ Успешно изменен Node ID: {current_node_id} -> {new_node_id}")

    except canopen.SdoCommunicationError as e:
        print(f"!!! Ошибка SDO: {e}")
    except Exception as e:
        print(f"!!! Ошибка: {e}")
    finally:
        network.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Изменение Node ID CANopen энкодера')
    parser.add_argument('current_id', type=int, help='Текущий Node ID')
    parser.add_argument('new_id', type=int, help='Новый Node ID')
    parser.add_argument('--channel',
                        default='can0',
                        help='CAN-интерфейс (по умолчанию: can0)')
    parser.add_argument('--bitrate',
                        type=int,
                        default=500000,
                        help='Скорость CAN (по умолчанию: 500000)')

    args = parser.parse_args()

    if not (1 <= args.new_id <= 127):
        print("!!! Новый Node ID должен быть в диапазоне 1-127")
    else:
        change_node_id(args.current_id, args.new_id, args.channel,
                       args.bitrate)
