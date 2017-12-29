package ya.yeeapp;

import android.os.StrictMode;
import android.support.v7.app.AppCompatActivity;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.EditText;

import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;

public class MainActivity extends AppCompatActivity {
    EditText editText;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        StrictMode.ThreadPolicy policy = new StrictMode.ThreadPolicy.Builder().permitAll().build();
        StrictMode.setThreadPolicy(policy);
        editText = (EditText) findViewById(R.id.editText);
    }

    @Override
    public void onResume(){
        super.onResume();
        editText.setText(udp("u").replaceAll("[^0-9]",""));
    }

    protected String udp(String msg){
        Log.e("test", msg);
        String re = "";
        try{
            DatagramSocket s = new DatagramSocket();
            byte[] buf = msg.getBytes();
            InetAddress a = InetAddress.getByName("192.168.0.4");
            DatagramPacket p = new DatagramPacket(buf, buf.length, a, 23232);
            s.send(p);
            if(msg.charAt(0) == 'u'){
                s.setSoTimeout(1000);
                buf = new byte[16];
                DatagramPacket rp = new DatagramPacket(buf, buf.length);
                s.receive(rp);
                re = new String(rp.getData());
            }
            s.close();
        }catch(Exception e){
            Log.e("test", "err", e);
        }
        return re;
    }
    public void toggle(View view) {
        udp("t");
    }
    public void movie(View view) {
       udp("m");
    }
    public void full(View view) {
        udp("f");
    }
    public void alarm(View view) {
        String time = editText.getText().toString();
        udp("a"+time);
    }
}

