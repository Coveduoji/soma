import { Tooltip } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';

/** 参数旁的小问号：悬停显示参数含义与调整效果。 */
export default function HelpTip({ text }: { text: string }) {
  return (
    <Tooltip title={text}>
      <QuestionCircleOutlined style={{ marginLeft: 4, color: '#999', cursor: 'help' }} />
    </Tooltip>
  );
}
