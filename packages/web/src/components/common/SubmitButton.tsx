import { Button, type ButtonProps } from '@astryxdesign/core/Button';

type Props = Pick<ButtonProps, 'label' | 'isLoading' | 'isDisabled'>;

// The full-width primary submit every auth and vault form ends with.
export default function SubmitButton(props: Props) {
  return <Button variant="primary" type="submit" width="100%" {...props} />;
}
