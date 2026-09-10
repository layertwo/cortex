import { Link, type LinkProps } from 'react-router-dom';

type Props = Omit<LinkProps, 'to'> & { href?: string };

// Astryx's LinkProvider hands every link an `href`; react-router's Link wants `to`.
// React 19 passes `ref` as an ordinary prop, so it flows through `...rest`.
export default function RouterLink({ href = '#', ...rest }: Props) {
  return <Link to={href} {...rest} />;
}
