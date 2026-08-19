type Props = {
  headerHeight: number;
  fontFamily: string;
  fontSize: string;
  rowWidth: string;
};

export function RuTaskListHeader({
  headerHeight,
  fontFamily,
  fontSize,
  rowWidth,
}: Props) {
  return (
    <div className="_3_ygE" style={{ fontFamily, fontSize }}>
      <div className="_1nBOt" style={{ height: headerHeight - 2 }}>
        <div className="_WuQ0f" style={{ minWidth: rowWidth }}>
          &nbsp;Задача
        </div>
        <div
          className="_2eZzQ"
          style={{ height: headerHeight * 0.5, marginTop: headerHeight * 0.2 }}
        />
        <div className="_WuQ0f" style={{ minWidth: rowWidth }}>
          &nbsp;Начало
        </div>
        <div
          className="_2eZzQ"
          style={{ height: headerHeight * 0.5, marginTop: headerHeight * 0.25 }}
        />
        <div className="_WuQ0f" style={{ minWidth: rowWidth }}>
          &nbsp;Конец
        </div>
      </div>
    </div>
  );
}
