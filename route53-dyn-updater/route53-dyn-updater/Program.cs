using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Net.Http;
using System.Security.Cryptography;
using System.IO;

/*
 * Instructions on HttpClient here: http://www.asp.net/web-api/overview/advanced/calling-a-web-api-from-a-net-client
 *  
 * requires Web API Client Libraries:
     * Use NuGet Package Manager to install the Web API Client Libraries package.
     * From the Tools menu, select Library Package Manager, then select Package Manager Console. In the Package Manager Console window, type the following command:
     * Install-Package Microsoft.AspNet.WebApi.Client
 */


namespace route53_dyn_updater
{
    class Program
    {
        static void Main(string[] args)
        {
            if (args.Length != 3)
            {
                string line = @"The script requires hostname and shared secret arguments
            ie: route53_dynamic_dns.exe host1.dyn.example.com. sharedsecret 'abc123.execute-api.us-west-2.amazonaws.com/prod'";
                Console.WriteLine(line);
                return;
            }
            string myHostname = args[0];
            string mySharedSecret = args[1];
            string myAPIURL = args[2];

            RunAsync(myHostname, mySharedSecret, myAPIURL).Wait();
        }
        static async Task RunAsync(string myHostname, string mySharedSecret, string myAPIURL)
        {
            using (var client = new HttpClient())
            {
                client.BaseAddress = new Uri(myAPIURL);
                client.DefaultRequestHeaders.Accept.Clear();
                client.DefaultRequestHeaders.Accept.Add(new System.Net.Http.Headers.MediaTypeWithQualityHeaderValue("application/json"));

                //get resource
                HttpResponseMessage response = await client.GetAsync("prod?mode=get");
                if (response.IsSuccessStatusCode)
                {
                    message myIP = await response.Content.ReadAsAsync<message>();
                    string hash = myIP.return_message + myHostname + mySharedSecret;
                    SHA256 mySHA256 = SHA256Managed.Create();
                    byte[] byteArray = Encoding.ASCII.GetBytes(hash);
                    MemoryStream stream = new MemoryStream(byteArray);

                    hash = byteArrayToString(mySHA256.ComputeHash(stream)).ToLower();

                    string command = "prod?mode=set&hostname=" + myHostname + "&hash=" + hash.ToLower();
                    HttpResponseMessage response1 = await client.GetAsync(command);
                    message response12 = await response1.Content.ReadAsAsync<message>();
                    Console.WriteLine(response12.return_message);

                }

            }
        }

        public class message
        {
            public string return_message { get; set; }
            public string return_status { get; set; }
        }

        public static string byteArrayToString(byte[] printString)
        {
            string output = "";
            for (int i = 0; i < printString.Length; i++)
            {
                output = output + String.Format("{0:X2}", printString[i]);
            }
            return output;
        }
    }
}
